#!/usr/bin/env python3
"""Run targeted real-API probes for the lightweight LLM Planner."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.config import get_settings  # noqa: E402
from app.models import ChatMessage, ChatRequest  # noqa: E402
from app.planner import build_planned_retrieval_message  # noqa: E402


DEFAULT_OUTPUT = ROOT / "data" / "tmp" / "evals" / "planner_probe_latest.jsonl"


CASES: dict[str, dict[str, Any]] = {
    "oral_budget_150": {
        "title": "口语预算：150 元以内防晒收窄",
        "message": "我的预算可能只有150",
        "history": [
            {"role": "user", "content": "夏天快到了，想看看防晒!"},
            {
                "role": "assistant",
                "content": "已返回商品卡片。",
                "product_ids": ["p_beauty_010", "p_beauty_023", "p_beauty_006"],
            },
            {"role": "user", "content": "我是油皮，主要是户外需求"},
        ],
        "expect": {"budget_value": 150.0},
    },
    "oral_budget_100": {
        "title": "口语预算：100 元以内防晒无结果边界",
        "message": "我的预算可能只有100",
        "history": [
            {"role": "user", "content": "夏天快到了，想看看防晒!"},
            {
                "role": "assistant",
                "content": "已返回商品卡片。",
                "product_ids": ["p_beauty_010", "p_beauty_023", "p_beauty_006"],
            },
            {"role": "user", "content": "我是油皮，主要是户外需求"},
        ],
        "expect": {"budget_value": 100.0},
    },
    "product_reference": {
        "title": "商品指代：第一款事实追问",
        "message": "第一款有没有酒精？",
        "history": [
            {"role": "user", "content": "我是油皮，想要200元以内通勤防晒"},
            {
                "role": "assistant",
                "content": "已返回商品卡片。",
                "product_ids": ["p_beauty_006"],
            },
        ],
        "expect": {"referenced_product_ids": ["p_beauty_006"]},
    },
    "exclude_inheritance": {
        "title": "排除继承：放宽预算不等于放宽排除条件",
        "message": "先放宽预算",
        "history": [
            {"role": "user", "content": "我是油皮，想要200元以内通勤防晒，不要酒精味太重或者刺激感强的产品。"},
            {
                "role": "assistant",
                "content": "已返回商品卡片。",
                "product_ids": ["p_beauty_006"],
            },
        ],
        "expect": {"budget_type": "relax"},
    },
    "generic_clarify": {
        "title": "泛需求：不应过度猜测",
        "message": "我想买护肤品，你推荐什么？",
        "history": [],
        "expect": {"needs_clarification": True, "allow_no_valid_delta": True},
    },
    "scene_bundle_sanya": {
        "title": "场景组合：三亚度假从防晒到穿搭",
        "message": "下周去三亚度假，帮我搭配一套从防晒到穿搭的方案",
        "history": [],
        "expect": {
            "recommendation_mode": "scene_bundle",
            "search_slot_categories": ["beauty", "apparel"],
            "search_slot_sub_categories_any": ["防晒", "短袖T恤", "速干T恤", "帽子", "运动短裤", "背包"],
        },
    },
    "scene_bundle_sunscreen_hat_pants": {
        "title": "场景组合：显式分别要防晒霜、帽子/防晒衣和裤子",
        "message": "能不能分别给我推荐一个防晒霜、一个帽子或者是防晒衣，然后再来个裤子？",
        "history": [],
        "expect": {
            "recommendation_mode": "scene_bundle",
            "search_slot_categories": ["beauty", "apparel"],
            "search_slot_sub_categories_any": ["防晒", "帽子", "运动短裤", "运动长裤", "户外裤"],
        },
    },
    "physical_sunscreen_non_cosmetic": {
        "title": "物理防晒：排除化妆品后应转成服饰防护候选",
        "message": "有没有什么？就是除了化妆品之外，比如说像防晒衣、防晒帽，嗯，就是物理防晒上的一些可以做的，就是推荐的东西。",
        "history": [
            {"role": "user", "content": "我可能马上要去三亚玩，然后想买一些防晒的东西，防晒的多件套的那种，你有什么推荐吗？"},
            {
                "role": "assistant",
                "content": "已返回防晒候选。",
                "product_ids": ["p_beauty_010", "p_beauty_023", "p_beauty_006"],
            },
        ],
        "expect": {
            "recommendation_mode_any": ["scene_bundle", "single_category"],
            "plan_categories_present": ["apparel"],
            "forbidden_plan_categories": ["beauty"],
            "plan_sub_categories_any": ["帽子", "速干T恤", "户外裤", "运动长裤", "运动短裤"],
        },
    },
}


def main() -> None:
    args = parse_args()
    if args.list_cases:
        for case_id, case in CASES.items():
            print(f"{case_id}\t{case['title']}")
        return

    settings = get_settings()
    if settings.mock_llm and not args.allow_mock:
        raise SystemExit(
            "Planner probe is a real-API benchmark. Set MOCK_LLM=false and provide active LLM config, "
            "or pass --allow-mock only for offline smoke checks."
        )
    if not settings.llm_configured and not args.allow_mock:
        raise SystemExit(
            "Missing active LLM key or model; planner probe needs real API config. "
            f"Current LLM_PROVIDER={settings.active_llm_provider}."
        )

    selected_case_ids = args.case or list(CASES)
    missing = [case_id for case_id in selected_case_ids if case_id not in CASES]
    if missing:
        raise SystemExit(f"Unknown planner probe case(s): {', '.join(missing)}")

    records = asyncio.run(run_cases(selected_case_ids, args.repeat))
    write_jsonl(args.output, records)
    print_summary(records, args.output)
    failures = [record for record in records if not record["passed"]]
    if failures:
        raise SystemExit(f"Planner probe failures: {len(failures)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", help="Case id to run. Repeat for multiple cases.")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-mock", action="store_true", help="Allow MOCK_LLM/fallback for offline smoke only.")
    parser.add_argument("--list-cases", action="store_true")
    return parser.parse_args()


async def run_cases(case_ids: list[str], repeat: int) -> list[dict[str, Any]]:
    settings = get_settings()
    records: list[dict[str, Any]] = []
    for round_index in range(1, repeat + 1):
        for case_id in case_ids:
            case = CASES[case_id]
            request = ChatRequest(
                message=case["message"],
                history=[
                    ChatMessage(
                        role=item["role"],
                        content=item["content"],
                        product_ids=item.get("product_ids", []),
                    )
                    for item in case["history"]
                ],
            )
            result = await build_planned_retrieval_message(settings, request)
            trace = result.trace.get("planner_trace", {})
            record = {
                "case_id": case_id,
                "title": case["title"],
                "round": round_index,
                "message": case["message"],
                "passed": True,
                "failures": [],
                "planner_trace": trace,
                "retrieval_message": result.message,
            }
            record["failures"] = evaluate(case.get("expect", {}), trace)
            record["passed"] = not record["failures"]
            records.append(record)
    return records


def evaluate(expectation: dict[str, Any], trace: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not trace.get("called"):
        failures.append("planner_not_called")
    fallback_reason = trace.get("fallback_reason")
    if fallback_reason and not (
        expectation.get("allow_no_valid_delta") and fallback_reason == "planner_no_valid_delta"
    ):
        failures.append(f"planner_fallback={trace.get('fallback_reason')}")
    validated = trace.get("validated_plan") or {}
    expected_clarification = expectation.get("needs_clarification")
    if expected_clarification is not None and validated.get("needs_clarification") != expected_clarification:
        failures.append(
            f"needs_clarification expected={expected_clarification} got={validated.get('needs_clarification')}"
        )
    if expected_clarification and not validated.get("clarification_question"):
        failures.append("missing_clarification_question")
    budget_update = validated.get("budget_update") or {}
    expected_budget = expectation.get("budget_value")
    if expected_budget is not None and budget_update.get("value") != expected_budget:
        failures.append(f"budget_value expected={expected_budget:g} got={budget_update.get('value')}")
    expected_budget_type = expectation.get("budget_type")
    if expected_budget_type is not None and budget_update.get("type") != expected_budget_type:
        failures.append(f"budget_type expected={expected_budget_type} got={budget_update.get('type')}")
    expected_refs = expectation.get("referenced_product_ids")
    if expected_refs is not None and validated.get("referenced_product_ids") != expected_refs:
        failures.append(f"referenced_product_ids expected={expected_refs} got={validated.get('referenced_product_ids')}")
    expected_mode = expectation.get("recommendation_mode")
    if expected_mode is not None and validated.get("recommendation_mode") != expected_mode:
        failures.append(f"recommendation_mode expected={expected_mode} got={validated.get('recommendation_mode')}")
    expected_modes = expectation.get("recommendation_mode_any")
    if expected_modes is not None and validated.get("recommendation_mode") not in expected_modes:
        failures.append(f"recommendation_mode expected_any={expected_modes} got={validated.get('recommendation_mode')}")
    expected_slot_categories = expectation.get("search_slot_categories")
    if expected_slot_categories is not None:
        slots = validated.get("search_slots") or []
        actual_categories = [slot.get("category") for slot in slots if isinstance(slot, dict)]
        missing = [category for category in expected_slot_categories if category not in actual_categories]
        if missing:
            failures.append(f"search_slot_categories missing={missing} got={actual_categories}")
    expected_any_sub_categories = expectation.get("search_slot_sub_categories_any")
    if expected_any_sub_categories:
        slots = validated.get("search_slots") or []
        actual_sub_categories: list[str] = []
        for slot in slots:
            if isinstance(slot, dict):
                actual_sub_categories.extend(str(item) for item in slot.get("sub_categories", []))
        if not set(expected_any_sub_categories).intersection(actual_sub_categories):
            failures.append(
                f"search_slot_sub_categories_any expected_any={expected_any_sub_categories} got={actual_sub_categories}"
            )
    expected_plan_categories = expectation.get("plan_categories_present")
    forbidden_plan_categories = expectation.get("forbidden_plan_categories")
    if expected_plan_categories or forbidden_plan_categories:
        actual_plan_categories = _plan_categories(validated)
        if expected_plan_categories:
            missing = [category for category in expected_plan_categories if category not in actual_plan_categories]
            if missing:
                failures.append(f"plan_categories missing={missing} got={actual_plan_categories}")
        if forbidden_plan_categories:
            present = [category for category in forbidden_plan_categories if category in actual_plan_categories]
            if present:
                failures.append(f"forbidden_plan_categories present={present} got={actual_plan_categories}")
    expected_plan_sub_categories = expectation.get("plan_sub_categories_any")
    if expected_plan_sub_categories:
        actual_plan_sub_categories = _plan_sub_categories(validated)
        if not set(expected_plan_sub_categories).intersection(actual_plan_sub_categories):
            failures.append(
                f"plan_sub_categories_any expected_any={expected_plan_sub_categories} got={actual_plan_sub_categories}"
            )
    return failures


def _plan_categories(validated: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    category_patch = validated.get("category_patch") or {}
    categories.extend(str(item) for item in category_patch.get("include", []) if item)
    for slot in validated.get("search_slots") or []:
        if isinstance(slot, dict) and slot.get("category"):
            categories.append(str(slot["category"]))
    return list(dict.fromkeys(categories))


def _plan_sub_categories(validated: dict[str, Any]) -> list[str]:
    sub_categories: list[str] = []
    facets_patch = validated.get("facets_patch") or {}
    sub_categories.extend(str(item) for item in facets_patch.get("sub_category", []) if item)
    for slot in validated.get("search_slots") or []:
        if isinstance(slot, dict):
            sub_categories.extend(str(item) for item in slot.get("sub_categories", []) if item)
    return list(dict.fromkeys(sub_categories))


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def print_summary(records: list[dict[str, Any]], output: Path) -> None:
    latencies = [
        int(record["planner_trace"].get("latency_ms"))
        for record in records
        if record["planner_trace"].get("latency_ms") is not None
    ]
    print(f"Wrote {len(records)} records to {output}")
    if latencies:
        sorted_latencies = sorted(latencies)
        p95_index = min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.95))
        print(f"Planner latency ms: median={median(sorted_latencies):g} p95={sorted_latencies[p95_index]} max={max(sorted_latencies)}")
    for record in records:
        status = "PASS" if record["passed"] else "FAIL"
        trace = record["planner_trace"]
        print(
            f"[{status}] {record['case_id']} round={record['round']} "
            f"latency_ms={trace.get('latency_ms')} applied={trace.get('applied')} "
            f"fallback={trace.get('fallback_reason')}"
        )
        for failure in record["failures"]:
            print(f"  - {failure}")


if __name__ == "__main__":
    main()
