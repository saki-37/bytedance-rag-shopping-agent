from threading import Lock
from typing import Any

from app.models import ConstraintChip, ConstraintOverrideSnapshot, ConstraintTrace


class ConstraintOverrideStore:
    """In-memory session override store for removable hard constraints."""

    def __init__(self) -> None:
        self._removed: dict[tuple[str, str], set[str]] = {}
        self._lock = Lock()

    def snapshot(self, user_id: str, conversation_id: str | None) -> ConstraintOverrideSnapshot:
        key = self._key(user_id, conversation_id)
        with self._lock:
            removed = sorted(self._removed.get(key, set()))
        return ConstraintOverrideSnapshot(removed_constraint_ids=removed)

    def remove(self, user_id: str, conversation_id: str | None, constraint_id: str) -> ConstraintOverrideSnapshot:
        normalized_id = normalize_constraint_id(constraint_id)
        key = self._key(user_id, conversation_id)
        with self._lock:
            self._removed.setdefault(key, set()).add(normalized_id)
            removed = sorted(self._removed[key])
        return ConstraintOverrideSnapshot(removed_constraint_ids=removed)

    @staticmethod
    def _key(user_id: str, conversation_id: str | None) -> tuple[str, str]:
        return (user_id.strip() or "local-demo-user", (conversation_id or "default").strip() or "default")


def constraint_id(kind: str, value: Any) -> str:
    normalized_kind = kind.strip()
    if normalized_kind == "budget_max":
        number = _as_float(value)
        if number is not None:
            return f"budget_max:{number:g}"
    return f"{normalized_kind}:{str(value).strip().lower()}"


def normalize_constraint_id(raw_id: str) -> str:
    if ":" not in raw_id:
        return raw_id.strip().lower()
    kind, value = raw_id.split(":", 1)
    return constraint_id(kind.strip(), value.strip())


def is_constraint_removed(
    overrides: ConstraintOverrideSnapshot | None,
    kind: str,
    value: Any,
) -> bool:
    if overrides is None:
        return False
    return constraint_id(kind, value) in set(overrides.removed_constraint_ids)


def filter_removed_terms(
    values: list[str],
    overrides: ConstraintOverrideSnapshot | None,
    kind: str,
) -> list[str]:
    return [value for value in values if not is_constraint_removed(overrides, kind, value)]


def constraint_chips_from_trace(trace: ConstraintTrace | dict[str, Any]) -> list[ConstraintChip]:
    payload = trace.model_dump(mode="json") if isinstance(trace, ConstraintTrace) else trace
    current_turn = _dict(payload.get("current_turn"))
    inherited = _dict(payload.get("inherited"))
    effective = _dict(payload.get("effective"))
    actions = [str(action) for action in payload.get("actions", []) if str(action)]

    chips: list[ConstraintChip] = []
    budget = effective.get("budget_max")
    if budget is not None:
        source = _source_for_budget(budget, current_turn, inherited, actions)
        chips.append(
            ConstraintChip(
                id=constraint_id("budget_max", budget),
                type="budget_max",
                label=f"{_format_number(budget)} 元以内",
                value=budget,
                source=source,
                scope=_scope_for_source(source),
                removable=True,
            )
        )

    for term in _string_list(effective.get("exclude_terms")):
        source = _source_for_term(term, "exclude_terms", current_turn, inherited, actions)
        chips.append(
            ConstraintChip(
                id=constraint_id("exclude_terms", term),
                type="exclude_terms",
                label=f"避开：{term}",
                value=term,
                source=source,
                scope=_scope_for_source(source),
                removable=True,
            )
        )

    for brand in _string_list(effective.get("brand_exclude")):
        source = _source_for_term(brand, "brand_exclude", current_turn, inherited, actions)
        chips.append(
            ConstraintChip(
                id=constraint_id("brand_exclude", brand),
                type="brand_exclude",
                label=f"排除品牌：{brand}",
                value=brand,
                source=source,
                scope=_scope_for_source(source),
                removable=True,
            )
        )

    return _dedupe_chips(chips)


def apply_override_to_constraints(
    constraints: dict[str, object],
    overrides: ConstraintOverrideSnapshot | None,
) -> dict[str, object]:
    if overrides is None or not overrides.removed_constraint_ids:
        return constraints
    updated = dict(constraints)
    budget = updated.get("budget_max")
    if budget is not None and is_constraint_removed(overrides, "budget_max", budget):
        updated.pop("budget_max", None)
    for key in ["exclude_terms", "brand_exclude"]:
        values = _string_list(updated.get(key))
        filtered = filter_removed_terms(values, overrides, key)
        if filtered:
            updated[key] = filtered
        else:
            updated.pop(key, None)
    return updated


def _source_for_budget(
    budget: Any,
    current_turn: dict[str, object],
    inherited: dict[str, object],
    actions: list[str],
) -> str:
    if _same_number(current_turn.get("budget_max"), budget):
        return "current_turn"
    if _same_number(inherited.get("budget_max"), budget):
        return "inherited"
    if any(action.startswith("budget_max:") for action in actions):
        return "memory"
    return "effective"


def _source_for_term(
    term: str,
    key: str,
    current_turn: dict[str, object],
    inherited: dict[str, object],
    actions: list[str],
) -> str:
    if term in _string_list(current_turn.get(key)):
        return "current_turn"
    if term in _string_list(inherited.get(key)):
        return "inherited"
    action_prefixes = {
        "exclude_terms": ("avoid_terms:", "recent_avoidance:"),
        "brand_exclude": ("brand_exclude:",),
    }.get(key, ())
    if any(action.startswith(action_prefixes) and term in action for action in actions):
        return "memory"
    return "effective"


def _scope_for_source(source: str) -> str:
    if source == "current_turn":
        return "turn"
    if source == "memory":
        return "profile"
    return "session"


def _dedupe_chips(chips: list[ConstraintChip]) -> list[ConstraintChip]:
    seen: set[str] = set()
    output: list[ConstraintChip] = []
    for chip in chips:
        if chip.id in seen:
            continue
        seen.add(chip.id)
        output.append(chip)
    return output


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_number(left: Any, right: Any) -> bool:
    left_value = _as_float(left)
    right_value = _as_float(right)
    if left_value is None or right_value is None:
        return False
    return abs(left_value - right_value) < 0.01


def _format_number(value: Any) -> str:
    number = _as_float(value)
    if number is None:
        return str(value)
    return f"{number:g}"
