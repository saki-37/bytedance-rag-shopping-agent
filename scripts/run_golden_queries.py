#!/usr/bin/env python3
"""Smoke-test backend SSE output with golden queries."""

from __future__ import annotations

import json
import urllib.request


BASE_URL = "http://127.0.0.1:8000"
QUERIES = [
    "我是油皮，想要 200 元以内的通勤防晒",
    "敏感肌最近屏障不稳定，想找修护面霜",
    "我想买护肤品，你推荐什么？",
]


def main() -> None:
    for query in QUERIES:
        debug = post_json("/api/debug/retrieve", {"message": query})
        trace = debug["trace"]
        product_ids = [product["product_id"] for product in debug["products"]]
        print(
            "TRACE",
            query,
            {
                "intent": trace["parsed_intent"],
                "products": product_ids,
                "final_ranking": trace["final_ranking"],
            },
        )
        if query == "我想买护肤品，你推荐什么？" and not debug["clarification_question"]:
            raise AssertionError("Expected clarification question for underspecified query")
        if "200" in query:
            over_budget = [product for product in debug["products"] if product["price"] > 200]
            if over_budget:
                raise AssertionError(f"Over-budget products returned: {over_budget}")

        req = urllib.request.Request(
            f"{BASE_URL}/api/chat/stream",
            data=json.dumps({"message": query}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        if "event: done" not in body or "event: products" not in body:
            raise AssertionError(f"Incomplete SSE for query: {query}\n{body[:500]}")
        print(f"OK {query}")


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


if __name__ == "__main__":
    main()
