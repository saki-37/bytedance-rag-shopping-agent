#!/usr/bin/env python3
"""Run the golden-query retrieval benchmark.

Default mode uses FastAPI's in-process TestClient, so it does not require a
running uvicorn server. Use `--mode http --check-stream` for live SSE smoke
tests against a local backend.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT = ROOT / "data" / "tmp" / "evals" / "golden_queries_latest.jsonl"


@dataclass(frozen=True)
class GoldenQuery:
    query_id: str
    query: str
    expected_facets: dict[str, list[str]] = field(default_factory=dict)
    expected_exclude_terms: list[str] = field(default_factory=list)
    expected_budget_max: float | None = None
    expected_any_product_ids: list[str] = field(default_factory=list)
    min_products: int = 1
    must_clarify: bool = False


GOLDEN_QUERIES = [
    GoldenQuery(
        query_id="GQ-01",
        query="我是油皮，想要 200 元以内的通勤防晒",
        expected_facets={"skin_type": ["油皮"], "effect": ["防晒"], "use_case": ["通勤"]},
        expected_budget_max=200,
        expected_any_product_ids=["p_beauty_006"],
    ),
    GoldenQuery(
        query_id="GQ-02",
        query="敏感肌最近屏障不稳定，想找修护面霜",
        expected_facets={"skin_type": ["敏感肌"], "effect": ["修护"]},
        expected_any_product_ids=["p_beauty_007", "p_beauty_012"],
    ),
    GoldenQuery(
        query_id="GQ-03",
        query="不要酒精味太重或者刺激感强的产品",
        expected_exclude_terms=["酒精", "刺激"],
    ),
    GoldenQuery(
        query_id="GQ-04",
        query="预算 300 内，有没有抗初老或者提亮精华",
        expected_facets={"effect": ["提亮", "抗初老"]},
        expected_budget_max=300,
        expected_any_product_ids=["p_beauty_018"],
    ),
    GoldenQuery(
        query_id="GQ-05",
        query="干皮想要保湿，不想拔干",
        expected_facets={"skin_type": ["干皮"], "effect": ["保湿"]},
        expected_any_product_ids=["p_beauty_012"],
    ),
    GoldenQuery(
        query_id="GQ-06",
        query="想要控油底妆或者定妆产品",
        expected_facets={"effect": ["控油", "底妆", "定妆"]},
        expected_any_product_ids=["p_beauty_020"],
    ),
    GoldenQuery(
        query_id="GQ-07",
        query="欧莱雅防晒和安热沙防晒更适合谁？",
        expected_facets={"effect": ["防晒"]},
        expected_any_product_ids=["p_beauty_006", "p_beauty_010"],
    ),
    GoldenQuery(
        query_id="GQ-08",
        query="我想买护肤品，你推荐什么？",
        min_products=0,
        must_clarify=True,
    ),
]


def main() -> None:
    args = parse_args()
    client = make_client(args.mode, args.base_url)
    records = []
    failures = []

    for spec in GOLDEN_QUERIES:
        debug = client.post_json("/api/debug/retrieve", {"message": spec.query})
        record = evaluate(spec, debug, require_vector=args.require_vector)

        if args.check_stream:
            stream_body = client.post_stream("/api/chat/stream", {"message": spec.query})
            if "event: done" not in stream_body or "event: products" not in stream_body:
                record["failures"].append("incomplete_sse_shape")
                record["passed"] = False

        records.append(record)
        status = "PASS" if record["passed"] else "FAIL"
        print(
            f"[{status}] {spec.query_id} products={record['products']} "
            f"clarify={bool(record['clarification_question'])} "
            f"vector_hits={record['vector_hits_count']}"
        )
        if record["failures"]:
            for failure in record["failures"]:
                print(f"  - {failure}")
            failures.append(spec.query_id)

    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} records to {args.output}")

    if failures:
        raise SystemExit(f"Golden query failures: {', '.join(failures)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["in-process", "http"], default="in-process")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check-stream", action="store_true")
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

    def post_stream(self, path: str, payload: dict[str, Any]) -> str:
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

    def post_stream(self, path: str, payload: dict[str, Any]) -> str:
        req = self._request(path, payload)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")

    def _request(self, path: str, payload: dict[str, Any]) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )


def evaluate(spec: GoldenQuery, debug: dict[str, Any], require_vector: bool) -> dict[str, Any]:
    products = debug["products"]
    trace = debug["trace"]
    intent = trace["parsed_intent"]
    product_ids = [product["product_id"] for product in products]
    vector_hits_count = len(trace["retrieval_channels"]["vector"])
    graph_hits_count = len(trace["retrieval_channels"]["graph"])
    failures: list[str] = []

    if spec.must_clarify:
        if not debug["clarification_question"]:
            failures.append("expected_clarification_question")
        if products:
            failures.append(f"expected_no_products_when_clarifying got={product_ids}")
    else:
        if debug["clarification_question"]:
            failures.append("unexpected_clarification_question")
        if len(products) < spec.min_products:
            failures.append(f"expected_at_least_{spec.min_products}_products got={len(products)}")

    if spec.expected_budget_max is not None:
        parsed_budget = intent["universal_constraints"]["budget_max"]
        if parsed_budget != spec.expected_budget_max:
            failures.append(f"budget_parse_mismatch expected={spec.expected_budget_max} got={parsed_budget}")
        over_budget = [product for product in products if product["price"] > spec.expected_budget_max]
        if over_budget:
            failures.append(f"over_budget_products={over_budget}")

    for facet_name, expected_values in spec.expected_facets.items():
        actual_values = intent["facets"].get(facet_name, [])
        missing = [value for value in expected_values if value not in actual_values]
        if missing:
            failures.append(f"missing_facet {facet_name}={missing} actual={actual_values}")

    missing_excludes = [
        term for term in spec.expected_exclude_terms if term not in intent["exclude_terms"]
    ]
    if missing_excludes:
        failures.append(f"missing_exclude_terms={missing_excludes}")

    if spec.expected_any_product_ids and not set(spec.expected_any_product_ids).intersection(product_ids):
        failures.append(f"missing_expected_product any_of={spec.expected_any_product_ids} got={product_ids}")

    if require_vector and not spec.must_clarify and vector_hits_count == 0:
        failures.append("expected_vector_hits")

    return {
        "id": spec.query_id,
        "query": spec.query,
        "passed": not failures,
        "failures": failures,
        "products": product_ids,
        "clarification_question": debug["clarification_question"],
        "parsed_intent": intent,
        "metadata_filter": trace.get("metadata_filter", {}),
        "filter_summary": trace.get("filter_summary", {}),
        "final_ranking": trace["final_ranking"],
        "ranking_signals": trace.get("ranking_signals", {}),
        "vector_hits_count": vector_hits_count,
        "graph_hits_count": graph_hits_count,
        "graph_hits": trace["retrieval_channels"]["graph"],
        "guardrail_checks": trace["guardrail_checks"],
        "constraint_trace": trace.get("constraint_trace", {}),
        "safety_trace": trace.get("safety_trace", {}),
        "source_trace": trace.get("source_trace", {}),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
