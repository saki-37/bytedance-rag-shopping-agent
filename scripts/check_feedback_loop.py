#!/usr/bin/env python3
"""Smoke-test the lightweight feedback loop."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))


def main() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    message = "我是油皮，想要200元以内通勤防晒"
    debug_response = client.post("/api/debug/retrieve", json={"message": message})
    debug_response.raise_for_status()
    debug = debug_response.json()

    feedback_payload = {
        "conversation_id": "feedback-smoke",
        "turn_id": "turn-1",
        "trace_id": debug["trace_id"],
        "message": message,
        "retrieval_message": debug["retrieval_message"],
        "answer": "这是一次用于验证反馈闭环的模拟回答。",
        "products": debug["products"],
        "trace": debug["trace"],
        "feedback": "inaccurate",
        "note": "Smoke test: record full retrieval snapshot for later review.",
    }
    feedback_response = client.post("/api/feedback", json=feedback_payload)
    feedback_response.raise_for_status()
    data = feedback_response.json()
    assert data["ok"] is True, data
    assert data["feedback"] == "inaccurate", data
    assert data["record_id"], data
    print(f"Feedback loop OK record_id={data['record_id']}")


if __name__ == "__main__":
    main()
