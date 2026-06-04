#!/usr/bin/env python3
"""Run an AI-assisted semantic review over benchmark JSONL records.

This script is intentionally generic: run any benchmark first, then pass the
result JSONL here. The deterministic runner result remains the first gate; this
review adds a second gate for semantic false-fails, false-passes, and groundedness
risks that keyword checks cannot catch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

DEFAULT_OUTPUT_DIR = ROOT / "data" / "tmp" / "evals"


SYSTEM_PROMPT = """你是电商 RAG 智能导购项目的 benchmark 语义核验员。
你会看到一条 benchmark 运行记录，其中可能包含用户问题、多轮对话、检索商品、机器判定 failures、模型回答、trace 摘要。
请基于记录本身判断：机器初筛是否可能误判、回答是否满足场景目标、是否存在资料外承诺或安全风险。

要求：
- 不要输出推理过程。
- 不要编造记录中没有的商品事实。
- 如果信息不足以裁定，标记 needs_human_review 或中等风险。
- 只输出一个 JSON 对象，不要 Markdown。

JSON schema:
{
  "semantic_score": 1到5的整数,
  "semantic_pass": true或false,
  "risk_level": "low"或"medium"或"high",
  "likely_false_fail": true或false,
  "likely_false_pass": true或false,
  "needs_human_review": true或false,
  "issues": [
    {
      "severity": "P0"或"P1"或"P2",
      "type": "retrieval"或"generation"或"groundedness"或"evaluation"或"safety"或"other",
      "message": "一句话说明问题"
    }
  ],
  "evidence_notes": ["最多3条简短依据"],
  "recommended_action": "一句话建议下一步"
}
"""


def main() -> None:
    args = parse_args()
    records = read_jsonl(args.input)
    if args.max_records is not None:
        records = records[: args.max_records]

    output = args.output or default_output_path(args.input)
    reviews: list[dict[str, Any]] = []

    client = None
    settings = None
    if not args.mock_review:
        from app.config import get_settings

        settings = get_settings()
        if not settings.ark_api_key or not settings.ark_model:
            raise SystemExit(
                "AI review requires ARK_API_KEY and ARK_MODEL in .env. "
                "Use --mock-review for an offline smoke test."
            )
        client = OpenAI(api_key=settings.ark_api_key, base_url=settings.ark_base_url)

    failures: list[str] = []
    for index, record in enumerate(records, start=1):
        compact = compact_record(record)
        if args.mock_review:
            review = mock_review(compact)
        else:
            assert client is not None and settings is not None
            review = call_ai_review(
                client=client,
                model=settings.ark_model,
                suite_name=args.suite_name or args.input.stem,
                compact_record=compact,
            )

        review_record = {
            "suite": args.suite_name or args.input.stem,
            "index": index,
            "id": record.get("id"),
            "title": record.get("title"),
            "deterministic_passed": record.get("passed"),
            "deterministic_failures": record.get("failures", []),
            "ai_review": review,
        }
        reviews.append(review_record)

        semantic_pass = bool(review.get("semantic_pass"))
        status = "PASS" if semantic_pass else "REVIEW"
        print(
            f"[{status}] {review_record['id']} "
            f"score={review.get('semantic_score')} "
            f"risk={review.get('risk_level')}"
        )
        if not semantic_pass:
            failures.append(str(record.get("id") or index))
        for issue in review.get("issues", [])[:3]:
            print(f"  - {issue.get('severity')} {issue.get('type')}: {issue.get('message')}")

    write_jsonl(output, reviews)
    print(f"Wrote {len(reviews)} AI review records to {output}")

    if args.strict and failures:
        raise SystemExit(f"AI semantic review flagged: {', '.join(failures)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="Benchmark JSONL output to review.")
    parser.add_argument("--output", type=Path, help="Review JSONL output path.")
    parser.add_argument("--suite-name", help="Human-readable suite name.")
    parser.add_argument("--max-records", type=int, help="Review only the first N records.")
    parser.add_argument("--mock-review", action="store_true", help="Offline deterministic smoke test; no API call.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any semantic review fails.")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def default_output_path(input_path: Path) -> Path:
    if input_path.parent.exists():
        return input_path.with_name(f"{input_path.stem}_ai_review.jsonl")
    return DEFAULT_OUTPUT_DIR / f"{input_path.stem}_ai_review.jsonl"


def compact_record(record: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "id",
        "title",
        "query",
        "passed",
        "failures",
        "products",
        "sub_categories",
        "comparison_mode",
        "clarification_question",
        "parsed_intent",
        "filter_summary",
        "ranking_signals",
        "guardrail_checks",
        "answer",
    ]
    compact = {key: record.get(key) for key in keys if key in record}
    if "turns" in record:
        compact["turns"] = [compact_turn(turn) for turn in record["turns"]]
    return truncate_value(compact)


def compact_turn(turn: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "turn_index",
        "user",
        "passed",
        "failures",
        "retrieval_message",
        "products",
        "stream_products",
        "clarification_question",
        "parsed_intent",
        "filter_summary",
        "ranking_signals",
        "guardrail_checks",
        "answer",
    ]
    return {key: turn.get(key) for key in keys if key in turn}


def truncate_value(value: Any, max_text: int = 1600, max_items: int = 12) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_text else f"{value[:max_text]}...[truncated]"
    if isinstance(value, list):
        return [truncate_value(item, max_text=max_text, max_items=max_items) for item in value[:max_items]]
    if isinstance(value, dict):
        return {
            key: truncate_value(item, max_text=max_text, max_items=max_items)
            for key, item in list(value.items())[:max_items]
        }
    return value


def call_ai_review(
    client: OpenAI,
    model: str,
    suite_name: str,
    compact_record: dict[str, Any],
) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Benchmark suite: {suite_name}\n"
                    "Benchmark record JSON:\n"
                    f"{json.dumps(compact_record, ensure_ascii=False, indent=2)}"
                ),
            },
        ],
    )
    content = response.choices[0].message.content or ""
    return parse_review_json(content)


def parse_review_json(content: str) -> dict[str, Any]:
    stripped = content.strip()
    try:
        return normalize_review(json.loads(stripped))
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return normalize_review(json.loads(stripped[start : end + 1]))
            except json.JSONDecodeError:
                pass
    return {
        "semantic_score": 1,
        "semantic_pass": False,
        "risk_level": "high",
        "likely_false_fail": False,
        "likely_false_pass": False,
        "needs_human_review": True,
        "issues": [
            {
                "severity": "P1",
                "type": "evaluation",
                "message": "AI review output was not valid JSON.",
            }
        ],
        "evidence_notes": [stripped[:500]],
        "recommended_action": "Inspect raw AI review output and rerun.",
    }


def normalize_review(review: dict[str, Any]) -> dict[str, Any]:
    score = review.get("semantic_score", 1)
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 1
    score = min(5, max(1, score))
    risk = review.get("risk_level")
    if risk not in {"low", "medium", "high"}:
        risk = "medium"
    issues = review.get("issues")
    if not isinstance(issues, list):
        issues = []
    return {
        "semantic_score": score,
        "semantic_pass": bool(review.get("semantic_pass", score >= 4)),
        "risk_level": risk,
        "likely_false_fail": bool(review.get("likely_false_fail", False)),
        "likely_false_pass": bool(review.get("likely_false_pass", False)),
        "needs_human_review": bool(review.get("needs_human_review", False)),
        "issues": issues[:8],
        "evidence_notes": review.get("evidence_notes", [])[:5]
        if isinstance(review.get("evidence_notes"), list)
        else [],
        "recommended_action": str(review.get("recommended_action", ""))[:500],
    }


def mock_review(record: dict[str, Any]) -> dict[str, Any]:
    passed = bool(record.get("passed"))
    failures = collect_failures(record)
    score = 4 if passed else 2
    return {
        "semantic_score": score,
        "semantic_pass": passed,
        "risk_level": "low" if passed else "medium",
        "likely_false_fail": False,
        "likely_false_pass": False,
        "needs_human_review": bool(failures),
        "issues": [
            {
                "severity": "P2",
                "type": "evaluation",
                "message": f"Mock review mirrors deterministic failures: {', '.join(failures[:3])}",
            }
        ]
        if failures
        else [],
        "evidence_notes": ["Mock review only checks deterministic pass/fail; use real AI review for semantic scoring."],
        "recommended_action": "Run without --mock-review for semantic verification.",
    }


def collect_failures(record: dict[str, Any]) -> list[str]:
    failures = list(record.get("failures", []) or [])
    for turn in record.get("turns", []) or []:
        failures.extend(turn.get("failures", []) or [])
    return [str(item) for item in failures]


if __name__ == "__main__":
    main()
