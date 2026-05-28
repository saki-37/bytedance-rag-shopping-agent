#!/usr/bin/env python3
"""Run multi-turn conversation regression cases for retrieval and clarification."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

DEFAULT_CASES = ROOT / "data" / "eval" / "conversation_cases.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT = ROOT / "data" / "tmp" / "evals" / "conversation_cases_latest.jsonl"


def main() -> None:
    args = parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    client = make_client(args.mode, args.base_url)
    records: list[dict[str, Any]] = []
    failures: list[str] = []

    for case in cases:
        record = run_case(case, client)
        records.append(record)
        status = "PASS" if record["passed"] else "FAIL"
        print(f"[{status}] {record['id']} {record['title']}")
        for turn in record["turns"]:
            products = turn["products"]
            clarify = bool(turn["clarification_question"])
            print(f"  turn={turn['turn_index']} products={products} clarify={clarify}")
            for failure in turn["failures"]:
                print(f"    - {failure}")
        if not record["passed"]:
            failures.append(record["id"])

    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} records to {args.output}")

    if failures:
        raise SystemExit(f"Conversation case failures: {', '.join(failures)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--mode", choices=["in-process", "http"], default="in-process")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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


class HttpClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))


def run_case(case: dict[str, Any], client: Any) -> dict[str, Any]:
    history: list[dict[str, str]] = []
    turn_records: list[dict[str, Any]] = []

    for turn_index, turn in enumerate(case["turns"], start=1):
        payload = {
            "message": turn["user"],
            "conversation_id": case["id"],
            "history": history,
        }
        debug = client.post_json("/api/debug/retrieve", payload)
        expectation = turn.get("expect")
        failures = evaluate_turn(expectation, debug) if expectation else []
        turn_records.append(
            {
                "turn_index": turn_index,
                "user": turn["user"],
                "passed": not failures,
                "failures": failures,
                "retrieval_message": debug.get("retrieval_message"),
                "products": [product["product_id"] for product in debug["products"]],
                "clarification_question": debug["clarification_question"],
                "parsed_intent": debug["trace"]["parsed_intent"],
                "metadata_filter": debug["trace"].get("metadata_filter", {}),
                "filter_summary": debug["trace"].get("filter_summary", {}),
                "ranking_signals": debug["trace"].get("ranking_signals", {}),
                "graph_hits_count": len(debug["trace"]["retrieval_channels"]["graph"]),
                "graph_hits": debug["trace"]["retrieval_channels"]["graph"],
                "guardrail_checks": debug["trace"]["guardrail_checks"],
            }
        )
        history.append({"role": "user", "content": turn["user"]})

    return {
        "id": case["id"],
        "title": case.get("title", ""),
        "passed": all(turn["passed"] for turn in turn_records),
        "turns": turn_records,
    }


def evaluate_turn(expectation: dict[str, Any], debug: dict[str, Any]) -> list[str]:
    products = debug["products"]
    product_ids = [product["product_id"] for product in products]
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
    if expected_any and not set(expected_any).intersection(product_ids):
        failures.append(f"missing_expected_product any_of={expected_any} got={product_ids}")

    forbidden_products = [product_id for product_id in expectation.get("forbidden_product_ids", []) if product_id in product_ids]
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

    return failures


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
