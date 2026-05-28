#!/usr/bin/env python3
"""Run comparison-query retrieval regression cases."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

DEFAULT_CASES = ROOT / "data" / "eval" / "comparison_queries.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT = ROOT / "data" / "tmp" / "evals" / "comparison_queries_latest.jsonl"


def main() -> None:
    args = parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    client = make_client(args.mode, args.base_url)
    records: list[dict[str, Any]] = []
    failures: list[str] = []

    for case in cases:
        debug = client.post_json("/api/debug/retrieve", {"message": case["query"]})
        record = evaluate(case, debug, require_vector=args.require_vector)
        records.append(record)
        status = "PASS" if record["passed"] else "FAIL"
        print(
            f"[{status}] {record['id']} products={record['products']} "
            f"comparison={record['comparison_mode']} vector_hits={record['vector_hits_count']}"
        )
        for failure in record["failures"]:
            print(f"  - {failure}")
        if not record["passed"]:
            failures.append(record["id"])

    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} records to {args.output}")

    if failures:
        raise SystemExit(f"Comparison query failures: {', '.join(failures)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--mode", choices=["in-process", "http"], default="in-process")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-vector", action="store_true")
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


def evaluate(case: dict[str, Any], debug: dict[str, Any], require_vector: bool) -> dict[str, Any]:
    expectation = case.get("expect", {})
    products = debug["products"]
    trace = debug["trace"]
    intent = trace["parsed_intent"]
    product_ids = [product["product_id"] for product in products]
    sub_categories = [product["sub_category"] for product in products]
    vector_hits_count = len(trace["retrieval_channels"]["vector"])
    failures: list[str] = []

    if debug["clarification_question"]:
        failures.append(f"unexpected_clarification_question={debug['clarification_question']}")
    if not intent.get("comparison_mode"):
        failures.append("expected_comparison_mode")

    min_products = expectation.get("min_products", 2)
    if len(products) < min_products:
        failures.append(f"expected_at_least_{min_products}_products got={len(products)}")

    missing_products = [
        product_id
        for product_id in expectation.get("expected_product_ids", [])
        if product_id not in product_ids
    ]
    if missing_products:
        failures.append(f"missing_expected_products={missing_products} got={product_ids}")

    allowed_sub_categories = expectation.get("allowed_sub_categories", [])
    if allowed_sub_categories:
        unexpected = sorted(set(sub_categories) - set(allowed_sub_categories))
        if unexpected:
            failures.append(f"unexpected_sub_categories={unexpected} allowed={allowed_sub_categories}")

    if require_vector and vector_hits_count == 0:
        failures.append("expected_vector_hits")

    return {
        "id": case["id"],
        "title": case.get("title", ""),
        "query": case["query"],
        "passed": not failures,
        "failures": failures,
        "products": product_ids,
        "sub_categories": sub_categories,
        "comparison_mode": intent.get("comparison_mode"),
        "parsed_intent": intent,
        "metadata_filter": trace.get("metadata_filter", {}),
        "filter_summary": trace.get("filter_summary", {}),
        "final_ranking": trace["final_ranking"],
        "ranking_signals": trace.get("ranking_signals", {}),
        "vector_hits_count": vector_hits_count,
        "guardrail_checks": trace["guardrail_checks"],
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
