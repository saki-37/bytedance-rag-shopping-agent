#!/usr/bin/env python3
"""Probe chat behavior without starting uvicorn or Android.

This uses the same FastAPI app endpoints in-process:
- /api/debug/retrieve for retrieval trace
- /api/chat/stream for SSE chat output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))


def main() -> None:
    args = parse_args()
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    history: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []

    for turn_index, message in enumerate(args.turn, start=1):
        payload = {
            "message": message,
            "conversation_id": "probe-chat",
            "history": history,
        }
        debug = post_json(client, "/api/debug/retrieve", payload)
        stream_text = post_text(client, "/api/chat/stream", payload)
        events = parse_sse(stream_text)
        answer = "".join(event["data"].get("token", "") for event in events if event["event"] == "token")
        statuses = [event["data"].get("status") for event in events if event["event"] == "status"]
        stream_products = [
            product["product_id"]
            for event in events
            if event["event"] == "products"
            for product in event["data"].get("products", [])
        ]
        record = {
            "turn_index": turn_index,
            "message": message,
            "retrieval_message": debug.get("retrieval_message"),
            "products": [product["product_id"] for product in debug["products"]],
            "stream_products": stream_products,
            "clarification_question": debug["clarification_question"],
            "parsed_intent": debug["trace"]["parsed_intent"],
            "guardrail_checks": debug["trace"]["guardrail_checks"],
            "statuses": statuses,
            "answer": answer,
        }
        records.append(record)
        print_turn(record)
        history.append({"role": "user", "content": message})
        if answer:
            history.append({"role": "assistant", "content": answer})

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"\nWrote {len(records)} records to {args.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--turn",
        action="append",
        required=True,
        help="User turn to send. Repeat --turn to simulate a multi-turn conversation.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSONL path for saving probe records.",
    )
    return parser.parse_args()


def post_json(client: Any, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def post_text(client: Any, path: str, payload: dict[str, Any]) -> str:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.text


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


def print_turn(record: dict[str, Any]) -> None:
    intent = record["parsed_intent"]
    print(f"\n=== Turn {record['turn_index']} ===")
    print(f"User: {record['message']}")
    print(f"Statuses: {', '.join(record['statuses'])}")
    print(f"Products: {record['products']}")
    print(f"Clarification: {record['clarification_question'] or '-'}")
    print(
        "Intent:",
        {
            "budget_max": intent["universal_constraints"]["budget_max"],
            "facets": intent["facets"],
            "exclude_terms": intent["exclude_terms"],
            "needs_clarification": intent["needs_clarification"],
        },
    )
    if record["retrieval_message"] != record["message"]:
        print("Retrieval message:")
        print(record["retrieval_message"])
    print("Answer:")
    print(record["answer"] or "-")


if __name__ == "__main__":
    main()
