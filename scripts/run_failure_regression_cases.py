#!/usr/bin/env python3
"""Run deterministic regressions promoted from real Android feedback."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.config import Settings  # noqa: E402
from app.conversation_state import build_retrieval_message  # noqa: E402
from app.data_loader import load_enriched_products, load_raw_products  # noqa: E402
from app.models import ChatMessage, ChatRequest  # noqa: E402
from app.retrieval import retrieve  # noqa: E402


DEFAULT_CASES = ROOT / "data" / "eval" / "failure_regression_cases.json"
DEFAULT_OUTPUT = ROOT / "data" / "tmp" / "evals" / "failure_regression_latest.jsonl"


def main() -> None:
    args = parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    settings = Settings(mock_llm=True)
    products = load_enriched_products(settings.enriched_data_dir, load_raw_products(settings.raw_data_dir))

    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for case in cases:
        record = run_case(case, products, settings)
        records.append(record)
        status = "PASS" if record["passed"] else "FAIL"
        print(f"[{status}] {record['id']} {record['title']}")
        for turn in record["turns"]:
            print(
                f"  turn={turn['turn_index']} products={turn['products']} "
                f"clarify={bool(turn['clarification_question'])} comparison={turn['comparison_mode']}"
            )
            for failure in turn["failures"]:
                print(f"    - {failure}")
        if not record["passed"]:
            failures.append(record["id"])

    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} records to {args.output}")
    if failures:
        raise SystemExit(f"Failure regression case failures: {', '.join(failures)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def run_case(case: dict[str, Any], products: list[dict[str, Any]], settings: Settings) -> dict[str, Any]:
    base_history = [ChatMessage.model_validate(item) for item in case.get("history", [])]
    sequential = bool(case.get("sequential", False))
    history = list(base_history)
    turn_records: list[dict[str, Any]] = []

    for turn_index, turn in enumerate(case["turns"], start=1):
        turn_history = history if sequential else [ChatMessage.model_validate(item) for item in turn.get("history", case.get("history", []))]
        request = ChatRequest(
            message=turn["user"],
            conversation_id=case["id"],
            history=turn_history,
        )
        retrieval_build = build_retrieval_message(request)
        result = retrieve(retrieval_build.message, products, index_dir=settings.index_dir)
        record = build_turn_record(turn_index, turn, retrieval_build, result)
        turn_records.append(record)

        if sequential:
            history.append(ChatMessage(role="user", content=turn["user"]))
            history.append(
                ChatMessage(
                    role="assistant",
                    content="已返回商品卡片。",
                    product_ids=record["products"],
                )
            )

    return {
        "id": case["id"],
        "title": case.get("title", ""),
        "source": case.get("source", ""),
        "passed": all(turn["passed"] for turn in turn_records),
        "turns": turn_records,
    }


def build_turn_record(
    turn_index: int,
    turn: dict[str, Any],
    retrieval_build: Any,
    result: Any,
) -> dict[str, Any]:
    trace = result.trace.model_dump(mode="json")
    intent = trace["parsed_intent"]
    products = [card.model_dump(mode="json") for card in result.cards]
    product_ids = [product["product_id"] for product in products]
    expectation = turn.get("expect") or {}
    debug = {
        "retrieval_message": retrieval_build.message,
        "conversation_state": retrieval_build.trace,
        "products": products,
        "clarification_question": result.clarification_question,
        "trace": trace,
    }
    failures = evaluate_turn(expectation, debug)
    return {
        "turn_index": turn_index,
        "user": turn["user"],
        "passed": not failures,
        "failures": failures,
        "retrieval_message": retrieval_build.message,
        "conversation_state": retrieval_build.trace,
        "products": product_ids,
        "clarification_question": result.clarification_question,
        "comparison_mode": intent.get("comparison_mode"),
        "parsed_intent": intent,
        "filter_summary": trace.get("filter_summary", {}),
        "final_ranking": trace.get("final_ranking", []),
        "ranking_signals": trace.get("ranking_signals", {}),
        "guardrail_checks": trace.get("guardrail_checks", {}),
        "constraint_trace": trace.get("constraint_trace", {}),
        "safety_trace": trace.get("safety_trace", {}),
        "source_trace": trace.get("source_trace", {}),
    }


def evaluate_turn(expectation: dict[str, Any], debug: dict[str, Any]) -> list[str]:
    products = debug["products"]
    product_ids = [product["product_id"] for product in products]
    categories = [product["category"] for product in products]
    sub_categories = [product["sub_category"] for product in products]
    clarification = debug["clarification_question"] or ""
    retrieval_message = debug.get("retrieval_message") or ""
    conversation_state = debug.get("conversation_state") or {}
    merged_state = conversation_state.get("state", {})
    intent = debug["trace"]["parsed_intent"]
    failures: list[str] = []

    if "must_clarify" in expectation:
        expected = bool(expectation["must_clarify"])
        actual = bool(clarification)
        if expected != actual:
            failures.append(f"clarification_mismatch expected={expected} got={actual} text={clarification}")

    if "expected_comparison_mode" in expectation:
        expected = bool(expectation["expected_comparison_mode"])
        actual = bool(intent.get("comparison_mode"))
        if expected != actual:
            failures.append(f"comparison_mode_mismatch expected={expected} got={actual}")

    if "min_products" in expectation and len(products) < expectation["min_products"]:
        failures.append(f"expected_min_products={expectation['min_products']} got={len(products)}")
    if "max_products" in expectation and len(products) > expectation["max_products"]:
        failures.append(f"expected_max_products={expectation['max_products']} got={len(products)}")

    expected_exact = expectation.get("expected_product_ids_exact", [])
    if expected_exact and product_ids != expected_exact:
        failures.append(f"product_ids_exact_mismatch expected={expected_exact} got={product_ids}")

    expected_prefix = expectation.get("expected_product_ids_prefix", [])
    if expected_prefix and product_ids[: len(expected_prefix)] != expected_prefix:
        failures.append(f"product_ids_prefix_mismatch expected={expected_prefix} got={product_ids}")

    expected_any = expectation.get("expected_any_product_ids", [])
    if expected_any and not set(expected_any).intersection(product_ids):
        failures.append(f"missing_expected_product any_of={expected_any} got={product_ids}")

    forbidden_products = [product_id for product_id in expectation.get("forbidden_product_ids", []) if product_id in product_ids]
    if forbidden_products:
        failures.append(f"forbidden_products_present={forbidden_products}")

    if "expected_referenced_product_ids" in expectation:
        expected = expectation["expected_referenced_product_ids"]
        actual = intent.get("referenced_product_ids", [])
        if actual != expected:
            failures.append(f"referenced_product_ids_mismatch expected={expected} got={actual}")
        state_actual = merged_state.get("referenced_product_ids", [])
        if state_actual and state_actual != expected:
            failures.append(f"state_referenced_product_ids_mismatch expected={expected} got={state_actual}")

    if "expected_budget_max" in expectation:
        expected = expectation["expected_budget_max"]
        actual = intent["universal_constraints"]["budget_max"]
        if actual != expected:
            failures.append(f"budget_parse_mismatch expected={expected} got={actual}")
        if actual is not None:
            over_budget = [product["product_id"] for product in products if product["price"] > actual]
            if over_budget:
                failures.append(f"over_budget_products={over_budget} budget={actual}")

    for facet_name, expected_values in expectation.get("expected_facets", {}).items():
        actual_values = intent.get("facets", {}).get(facet_name, [])
        missing = [value for value in expected_values if value not in actual_values]
        if missing:
            failures.append(f"missing_facet {facet_name}={missing} actual={actual_values}")

    for term in expectation.get("expected_exclude_terms", []):
        if term not in intent.get("exclude_terms", []):
            failures.append(f"missing_exclude_term={term} actual={intent.get('exclude_terms', [])}")

    if "expected_category_candidates" in expectation:
        expected = expectation["expected_category_candidates"]
        actual = intent.get("category_candidates", [])
        if actual != expected:
            failures.append(f"category_candidates_mismatch expected={expected} got={actual}")

    forbidden_category_candidates = [
        category
        for category in expectation.get("forbidden_category_candidates", [])
        if category in intent.get("category_candidates", [])
    ]
    if forbidden_category_candidates:
        failures.append(f"forbidden_category_candidates_present={forbidden_category_candidates}")

    check_allowed("product_categories", categories, expectation.get("allowed_product_categories", []), failures)
    check_forbidden("product_categories", categories, expectation.get("forbidden_product_categories", []), failures)
    check_allowed("product_sub_categories", sub_categories, expectation.get("allowed_product_sub_categories", []), failures)
    check_forbidden("product_sub_categories", sub_categories, expectation.get("forbidden_product_sub_categories", []), failures)

    for text in expectation.get("clarification_contains", []):
        if text not in clarification:
            failures.append(f"clarification_missing_text={text}")
    for text in expectation.get("retrieval_message_contains", []):
        if text not in retrieval_message:
            failures.append(f"retrieval_message_missing_text={text}")
    for text in expectation.get("retrieval_message_not_contains", []):
        if text in retrieval_message:
            failures.append(f"retrieval_message_forbidden_text={text}")

    return failures


def check_allowed(label: str, actual_values: list[str], allowed_values: list[str], failures: list[str]) -> None:
    if not allowed_values:
        return
    unexpected = sorted(set(actual_values) - set(allowed_values))
    if unexpected:
        failures.append(f"unexpected_{label}={unexpected} allowed={allowed_values}")


def check_forbidden(label: str, actual_values: list[str], forbidden_values: list[str], failures: list[str]) -> None:
    if not forbidden_values:
        return
    present = sorted(set(actual_values).intersection(forbidden_values))
    if present:
        failures.append(f"forbidden_{label}_present={present}")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
