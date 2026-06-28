#!/usr/bin/env python3
"""Verify session-scoped constraint chip removal without external LLM calls."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
os.environ["MOCK_LLM"] = "true"


def main() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    user_id = "constraint-state-test-user"
    conversation_id = "constraint-state-test-a"
    next_conversation_id = "constraint-state-test-b"
    history_conversation_id = "constraint-state-test-history"
    failures: list[str] = []

    put_profile(client, user_id)

    first = debug_retrieve(client, user_id, conversation_id, "推荐一款适合通勤的防晒")
    first_effective = effective_constraints(first)
    if first_effective.get("budget_max") != 200.0:
        failures.append(f"expected profile budget 200 before removal, got {first_effective.get('budget_max')}")
    if "酒精" not in first_effective.get("exclude_terms", []):
        failures.append(f"expected profile exclude term 酒精 before removal, got {first_effective.get('exclude_terms')}")
    if not any(chip.get("id") == "budget_max:200" for chip in first.get("constraints", [])):
        failures.append(f"expected budget chip before removal, got {first.get('constraints')}")

    remove_constraint(client, user_id, conversation_id, "budget_max:200")
    no_budget = debug_retrieve(client, user_id, conversation_id, "推荐一款适合通勤的防晒")
    no_budget_effective = effective_constraints(no_budget)
    if no_budget_effective.get("budget_max") == 200.0:
        failures.append(f"budget override did not apply: {no_budget_effective}")
    if any(chip.get("id") == "budget_max:200" for chip in no_budget.get("constraints", [])):
        failures.append(f"budget chip still visible after removal: {no_budget.get('constraints')}")

    remove_constraint(client, user_id, conversation_id, "exclude_terms:酒精")
    no_exclude = debug_retrieve(client, user_id, conversation_id, "推荐一款适合通勤的防晒")
    no_exclude_effective = effective_constraints(no_exclude)
    if "酒精" in no_exclude_effective.get("exclude_terms", []):
        failures.append(f"exclude override did not apply: {no_exclude_effective}")

    remove_constraint(client, user_id, history_conversation_id, "budget_max:200")
    remove_constraint(client, user_id, history_conversation_id, "exclude_terms:酒精")
    history_followup = debug_retrieve(
        client,
        user_id,
        history_conversation_id,
        "换一批",
        history=[{"role": "user", "content": "200以内，不要酒精，推荐防晒"}],
    )
    history_effective = effective_constraints(history_followup)
    if history_effective.get("budget_max") == 200.0 or "酒精" in history_effective.get("exclude_terms", []):
        failures.append(f"history constraints leaked after removal: {history_effective}")

    explicit_readd = debug_retrieve(client, user_id, history_conversation_id, "200以内，推荐防晒")
    explicit_readd_effective = effective_constraints(explicit_readd)
    if explicit_readd_effective.get("budget_max") != 200.0:
        failures.append(f"explicit current-turn budget should reapply after removal, got {explicit_readd_effective}")

    new_session = debug_retrieve(client, user_id, next_conversation_id, "推荐一款适合通勤的防晒")
    new_session_effective = effective_constraints(new_session)
    if new_session_effective.get("budget_max") != 200.0:
        failures.append(f"new conversation should still read profile budget, got {new_session_effective}")
    if "酒精" not in new_session_effective.get("exclude_terms", []):
        failures.append(f"new conversation should still read profile avoid term, got {new_session_effective}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)
    print("PASS constraint state overrides")


def put_profile(client: "TestClient", user_id: str) -> None:
    from app.main import memory_provider
    from app.models import RecipientProfile, UserMemoryConstraints, UserMemoryProfile
    from app.user_memory import MemoryUpdateEvent

    profile = UserMemoryProfile(
        user_id=user_id,
        constraints=UserMemoryConstraints(avoid_terms=["酒精"], budget_max=200),
        recipients=[
            RecipientProfile(
                recipient_id="self",
                display_name="自己",
                relationship="self",
                constraints=UserMemoryConstraints(avoid_terms=["酒精"], budget_max=200),
            )
        ],
        selected_recipient_id="self",
    )
    memory_provider.update_profile(user_id, MemoryUpdateEvent(profile=profile))


def debug_retrieve(
    client: "TestClient",
    user_id: str,
    conversation_id: str,
    message: str,
    history: list[dict[str, str]] | None = None,
) -> dict:
    response = client.post(
        "/api/debug/retrieve",
        json={
            "user_id": user_id,
            "conversation_id": conversation_id,
            "recipient_id": "self",
            "message": message,
            "history": history or [],
        },
    )
    response.raise_for_status()
    return response.json()


def remove_constraint(client: "TestClient", user_id: str, conversation_id: str, constraint_id: str) -> None:
    response = client.post(
        f"/api/conversations/{conversation_id}/constraint-actions",
        json={
            "user_id": user_id,
            "recipient_id": "self",
            "action": "remove",
            "constraint_id": constraint_id,
        },
    )
    response.raise_for_status()


def effective_constraints(payload: dict) -> dict:
    return payload.get("trace", {}).get("constraint_trace", {}).get("effective", {})


if __name__ == "__main__":
    main()
