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


if __name__ == "__main__":
    main()
