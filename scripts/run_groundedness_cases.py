#!/usr/bin/env python3
"""Run groundedness / anti-hallucination benchmark cases.

This runner exercises the same FastAPI endpoints used by the Android demo:
- /api/debug/retrieve for parsed intent, retrieval trace, and product cards
- /api/chat/stream for SSE generation output

By default it uses the app's normal settings. Pass --mock-llm for a stable,
local-only run that avoids external model calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

DEFAULT_CASES = ROOT / "data" / "eval" / "groundedness_cases.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT = ROOT / "data" / "tmp" / "evals" / "groundedness_cases_latest.jsonl"


def main() -> None:
    args = parse_args()
    if args.mock_llm:
        os.environ["MOCK_LLM"] = "true"

    payload = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = payload["cases"] if isinstance(payload, dict) and "cases" in payload else payload
    client = make_client(args.mode, args.base_url)
    records: list[dict[str, Any]] = []
    failures: list[str] = []

    for case in cases:
        if args.case_id and case["id"] not in args.case_id:
            continue
        record = run_case(case, client, skip_answer_checks=args.retrieval_only)
        records.append(record)
        status = "PASS" if record["passed"] else "FAIL"
        print(f"[{status}] {record['id']} {record.get('title', '')}")
        for turn in record["turns"]:
            print(
                "  "
                f"turn={turn['turn_index']} "
                f"products={turn['products']} "
                f"clarify={bool(turn['clarification_question'])} "
                f"answer_len={len(turn['answer'])}"
            )
            for failure in turn["failures"]:
                print(f"    - {failure}")
        if not record["passed"]:
            failures.append(record["id"])

    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} records to {args.output}")

    if failures:
        raise SystemExit(f"Groundedness case failures: {', '.join(failures)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--mode", choices=["in-process", "http"], default="in-process")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-id", action="append", help="Run only selected case id. Repeatable.")
    parser.add_argument("--mock-llm", action="store_true", help="Force local mock generation for deterministic offline runs.")
    parser.add_argument("--retrieval-only", action="store_true", help="Skip generated-answer substring checks.")
    return parser.parse_args()


def make_client(mode: str, base_url: str):
    if mode == "http":
        return HttpClient(base_url=base_url)
    return InProcessClient()


class InProcessClient:
    def __init__(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        self.client = TestClient(app)

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def post_text(self, path: str, payload: dict[str, Any]) -> str:
        response = self.client.post(path, json=payload)
        response.raise_for_status()
        return response.text


class HttpClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = self._request(path, payload)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def post_text(self, path: str, payload: dict[str, Any]) -> str:
        req = self._request(path, payload)
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read().decode("utf-8")

    def _request(self, path: str, payload: dict[str, Any]) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )


def run_case(case: dict[str, Any], client: Any, skip_answer_checks: bool) -> dict[str, Any]:
    history: list[dict[str, Any]] = []
    turn_records: list[dict[str, Any]] = []

    for turn_index, turn in enumerate(case["turns"], start=1):
        payload = {
            "message": turn["user"],
            "conversation_id": case["id"],
            "history": history,
        }
        debug = client.post_json("/api/debug/retrieve", payload)
        stream_body = client.post_text("/api/chat/stream", payload)
        events = parse_sse(stream_body)
        answer = "".join(event["data"].get("token", "") for event in events if event["event"] == "token")
        stream_products = [
            product["product_id"]
            for event in events
            if event["event"] == "products"
            for product in event["data"].get("products", [])
        ]
        failures = evaluate_turn(
            expectation=turn.get("expect", {}),
            debug=debug,
            answer=answer,
            stream_products=stream_products,
            skip_answer_checks=skip_answer_checks,
        )
        turn_record = build_turn_record(
            turn_index=turn_index,
            user_message=turn["user"],
            debug=debug,
            answer=answer,
            stream_products=stream_products,
            failures=failures,
        )
        turn_records.append(turn_record)
        product_ids = [product["product_id"] for product in debug["products"]]
        assistant_product_ids = list(dict.fromkeys([*product_ids, *stream_products]))
        history.append({"role": "user", "content": turn["user"]})
        if answer or assistant_product_ids:
            history.append(
                {
                    "role": "assistant",
                    "content": answer or "已返回商品卡片。",
                    "product_ids": assistant_product_ids,
                }
            )

    return {
        "id": case["id"],
        "title": case.get("title", ""),
        "case_type": case.get("case_type"),
        "difficulty": case.get("difficulty"),
        "passed": all(not turn["failures"] for turn in turn_records),
        "turns": turn_records,
    }


def evaluate_turn(
    expectation: dict[str, Any],
    debug: dict[str, Any],
    answer: str,
    stream_products: list[str],
    skip_answer_checks: bool,
) -> list[str]:
    products = debug["products"]
    product_ids = [product["product_id"] for product in products]
    all_product_ids = list(dict.fromkeys([*product_ids, *stream_products]))
    clarification = debug["clarification_question"] or ""
    retrieval_message = debug.get("retrieval_message") or ""
    intent = debug["trace"]["parsed_intent"]
    failures: list[str] = []

    if "must_clarify" in expectation:
        must_clarify = bool(expectation["must_clarify"])
        if must_clarify and not clarification:
            failures.append("expected_clarification_question")
        if not must_clarify and clarification:
            failures.append(f"unexpected_clarification_question={clarification}")

    if "min_products" in expectation and len(products) < expectation["min_products"]:
        failures.append(f"expected_min_products={expectation['min_products']} got={len(products)}")

    if "max_products" in expectation and len(products) > expectation["max_products"]:
        failures.append(f"expected_max_products={expectation['max_products']} got={len(products)}")

    if "expected_budget_max" in expectation:
        parsed_budget = intent["universal_constraints"]["budget_max"]
        if parsed_budget != expectation["expected_budget_max"]:
            failures.append(f"budget_parse_mismatch expected={expectation['expected_budget_max']} got={parsed_budget}")
        if parsed_budget is not None:
            over_budget = [product["product_id"] for product in products if product["price"] > parsed_budget]
            if over_budget:
                failures.append(f"over_budget_products={over_budget} budget={parsed_budget}")

    if "max_product_price" in expectation:
        over_price = [product["product_id"] for product in products if product["price"] > expectation["max_product_price"]]
        if over_price:
            failures.append(f"over_max_product_price={over_price} max={expectation['max_product_price']}")

    for facet_name, expected_values in expectation.get("expected_facets", {}).items():
        actual_values = intent["facets"].get(facet_name, [])
        missing = [value for value in expected_values if value not in actual_values]
        if missing:
            failures.append(f"missing_facet {facet_name}={missing} actual={actual_values}")

    for term in expectation.get("expected_exclude_terms", []):
        if term not in intent["exclude_terms"]:
            failures.append(f"missing_exclude_term={term} actual={intent['exclude_terms']}")

    expected_any = expectation.get("expected_any_product_ids", [])
    if expected_any and not set(expected_any).intersection(all_product_ids):
        failures.append(f"missing_expected_product any_of={expected_any} got={all_product_ids}")

    forbidden_products = [product_id for product_id in expectation.get("forbidden_product_ids", []) if product_id in all_product_ids]
    if forbidden_products:
        failures.append(f"forbidden_products_present={forbidden_products}")

    for text in expectation.get("clarification_contains", []):
        if text not in clarification:
            failures.append(f"clarification_missing_text={text}")

    for text in expectation.get("clarification_not_contains", []):
        if text in clarification:
            failures.append(f"clarification_forbidden_text={text}")

    for text in expectation.get("retrieval_message_contains", []):
        if text not in retrieval_message:
            failures.append(f"retrieval_message_missing_text={text}")

    if not skip_answer_checks:
        for text in expectation.get("answer_must_contain", []):
            if text not in answer:
                failures.append(f"answer_missing_text={text}")

        for text in expectation.get("answer_must_not_contain", []):
            if text in answer:
                failures.append(f"answer_forbidden_text={text}")

    return failures


def build_turn_record(
    turn_index: int,
    user_message: str,
    debug: dict[str, Any],
    answer: str,
    stream_products: list[str],
    failures: list[str],
) -> dict[str, Any]:
    trace = debug["trace"]
    return {
        "turn_index": turn_index,
        "user": user_message,
        "passed": not failures,
        "failures": failures,
        "retrieval_message": debug.get("retrieval_message"),
        "products": [product["product_id"] for product in debug["products"]],
        "stream_products": stream_products,
        "clarification_question": debug["clarification_question"],
        "parsed_intent": trace["parsed_intent"],
        "metadata_filter": trace.get("metadata_filter", {}),
        "filter_summary": trace.get("filter_summary", {}),
        "final_ranking": trace["final_ranking"],
        "ranking_signals": trace.get("ranking_signals", {}),
        "guardrail_checks": trace["guardrail_checks"],
        "answer": answer,
    }


def parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event_name = ""
    data_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
        elif not line.strip() and event_name:
            raw_data = "\n".join(data_lines)
            data = json.loads(raw_data) if raw_data else {}
            events.append({"event": event_name, "data": data})
            event_name = ""
            data_lines = []
    return events


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
