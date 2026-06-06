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
            "Planner probe is a real-API benchmark. Set MOCK_LLM=false and provide Ark config, "
            "or pass --allow-mock only for offline smoke checks."
        )
    if (not settings.ark_api_key or not settings.ark_model) and not args.allow_mock:
        raise SystemExit("Missing ARK_API_KEY or ARK_MODEL; planner probe needs real API config.")

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
    return failures


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
