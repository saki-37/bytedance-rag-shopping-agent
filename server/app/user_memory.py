from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import logging
import re
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.models import (
    ChatRequest,
    MemorySearchHit,
    MemorySnapshot,
    MemorySourceEvent,
    MemoryTrace,
    UserMemoryProfile,
    UserMemoryConstraints,
    UserMemoryInteractionPreferences,
)

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_USER_ID = "local-demo-user"
MEMORY_PROVIDER_LOCAL = "local"
MEMORY_PROVIDER_MEM0 = "mem0"
MEMORY_PROVIDER_DISABLED = "disabled"


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class MemoryUpdateEvent:
    def __init__(self, profile: UserMemoryProfile | None = None, note: str | None = None):
        self.profile = profile
        self.note = note


class MemoryProvider(Protocol):
    def get_profile(self, user_id: str) -> UserMemoryProfile:
        ...

    def update_profile(self, user_id: str, event: MemoryUpdateEvent) -> UserMemoryProfile:
        ...

    def search_soft_memory(self, user_id: str, query: str, limit: int = 5) -> list[MemorySearchHit]:
        ...


class DisabledMemoryProvider:
    def get_profile(self, user_id: str) -> UserMemoryProfile:
        return _default_profile(user_id)

    def update_profile(self, user_id: str, event: MemoryUpdateEvent) -> UserMemoryProfile:
        return self.get_profile(user_id)

    def search_soft_memory(self, user_id: str, query: str, limit: int = 5) -> list[MemorySearchHit]:
        return []


class LocalMemoryProvider:
    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def get_profile(self, user_id: str) -> UserMemoryProfile:
        user_id = _sanitize_user_id(user_id)
        profile_path = self._profile_path(user_id)
        if not profile_path.exists():
            profile = _default_profile(user_id)
            _write_profile(profile_path, profile)
            return profile
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("memory file is not a JSON object")
            if data.get("user_id") != user_id:
                data["user_id"] = user_id
            return _normalize_profile(UserMemoryProfile.model_validate(data))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to load memory profile from %s; fallback to default: %s", profile_path, exc)
            return _default_profile(user_id)

    def update_profile(self, user_id: str, event: MemoryUpdateEvent) -> UserMemoryProfile:
        user_id = _sanitize_user_id(user_id)
        if event.profile is None:
            return self.get_profile(user_id)
        profile = _normalize_profile(event.profile.model_copy(update={"user_id": user_id, "updated_at": _utc_now_iso()}))
        _write_profile(self._profile_path(user_id), profile)
        return profile

    def search_soft_memory(self, user_id: str, query: str, limit: int = 5) -> list[MemorySearchHit]:
        profile = self.get_profile(user_id)
        term = query.lower().strip()
        if not term:
            return []
        hits: list[MemorySearchHit] = []
        for snapshot in profile.short_term_snapshots.recent_interests:
            if snapshot.key.lower() in term:
                hits.append(MemorySearchHit(key=snapshot.key, score=snapshot.weight, source=snapshot.source))
        for snapshot in profile.short_term_snapshots.recent_avoidance:
            if snapshot.key.lower() in term:
                hits.append(MemorySearchHit(key=snapshot.key, score=snapshot.weight, source=snapshot.source))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]

    def _profile_path(self, user_id: str) -> Path:
        return self.memory_dir / f"{_sanitize_user_id(user_id)}.json"


def get_memory_provider(settings: Settings) -> MemoryProvider:
    provider = settings.memory_provider.strip().lower()
    if provider == MEMORY_PROVIDER_DISABLED:
        return DisabledMemoryProvider()
    if provider == MEMORY_PROVIDER_MEM0:
        return DisabledMemoryProvider()
    return LocalMemoryProvider(settings.memory_dir)


def resolve_user_id(request: ChatRequest, default_user_id: str = DEFAULT_MEMORY_USER_ID) -> str:
    if request.user_id:
        return request.user_id.strip() or default_user_id
    if request.conversation_id:
        return request.conversation_id.strip() or default_user_id
    return default_user_id


def build_memory_augmented_request(
    request: ChatRequest,
    memory_profile: UserMemoryProfile,
) -> tuple[ChatRequest, list[str], dict[str, object], list[str]]:
    now = datetime.now(UTC)
    context_lines = memory_context_lines(memory_profile, now=now)
    if not context_lines:
        return request, [], {}, []

    prefix = "历史记忆约束（不直接向用户暴露）：\n" + "\n".join(context_lines) + "\n\n"
    augmented_message = f"{prefix}{request.message}"
    applied_constraints = _collect_applied_constraints(memory_profile)
    applied_short_term_signals = _collect_applied_short_term_signals(memory_profile, now=now)
    return (
        request.model_copy(update={"message": augmented_message}),
        context_lines,
        applied_constraints,
        applied_short_term_signals,
    )


def memory_context_lines(memory_profile: UserMemoryProfile, now: datetime | None = None) -> list[str]:
    reference_time = now or datetime.now(UTC)
    lines: list[str] = []
    constraints = memory_profile.constraints
    if constraints.budget_max is not None:
        lines.append(f"- 硬约束：预算上限 {constraints.budget_max:g} 元")
    if constraints.avoid_terms:
        lines.append(f"- 硬约束：避免关键词 { '、'.join(constraints.avoid_terms)}")
    if constraints.brand_exclude:
        lines.append(f"- 硬约束：排除品牌 { '、'.join(constraints.brand_exclude)}")
    active_interests = _active_memory_snapshots(memory_profile.short_term_snapshots.recent_interests, now=reference_time)
    if active_interests:
        items = [snapshot.key for snapshot in active_interests[:3] if snapshot.key]
        if items:
            lines.append(f"- 短期兴趣：{ '、'.join(items)}")
    active_avoidance = _active_memory_snapshots(memory_profile.short_term_snapshots.recent_avoidance, now=reference_time)
    if active_avoidance:
        items = [snapshot.key for snapshot in active_avoidance[:3] if snapshot.key]
        if items:
            lines.append(f"- 最近回避：{ '、'.join(items)}")
    if memory_profile.interaction_preferences.answer_length != "normal":
        lines.append(f"- 回答风格：{memory_profile.interaction_preferences.answer_length}")
    return lines


def _collect_applied_short_term_signals(
    memory_profile: UserMemoryProfile,
    now: datetime | None = None,
) -> list[str]:
    reference_time = now or datetime.now(UTC)
    signals: list[str] = []
    for snapshot in _active_memory_snapshots(memory_profile.short_term_snapshots.recent_interests, now=reference_time):
        if snapshot.key:
            signals.append(f"recent_interest:{snapshot.key}:{snapshot.weight:.2f}")
    for snapshot in _active_memory_snapshots(memory_profile.short_term_snapshots.recent_avoidance, now=reference_time):
        if snapshot.key:
            signals.append(f"recent_avoidance:{snapshot.key}:{snapshot.weight:.2f}")
    return signals


def build_memory_trace(
    provider: str,
    user_id: str,
    memory_profile: UserMemoryProfile,
    applied_constraints: dict[str, object],
    applied_short_term_signals: list[str],
    applied_preferences: dict[str, object],
    skipped: list[str],
    fallback: str | None = None,
) -> MemoryTrace:
    return MemoryTrace(
        provider=provider,
        user_id=user_id,
        enabled=provider != MEMORY_PROVIDER_DISABLED,
        applied_constraints=applied_constraints,
        applied_short_term_signals=applied_short_term_signals,
        applied_preferences=applied_preferences,
        skipped_items=skipped,
        fallback=fallback,
    )


def _collect_applied_constraints(memory_profile: UserMemoryProfile) -> dict[str, object]:
    constraints = memory_profile.constraints
    return {
        "constraints": {
            "allergies": constraints.allergies,
            "avoid_terms": constraints.avoid_terms,
            "brand_exclude": constraints.brand_exclude,
            "budget_max": constraints.budget_max,
            "accessibility_needs": constraints.accessibility_needs,
        },
        "long_term_preferences": {
            "preferred_categories": memory_profile.long_term_preferences.preferred_categories,
            "preferred_tags": memory_profile.long_term_preferences.preferred_tags,
        },
    }


def _active_memory_snapshots(
    snapshots: list[MemorySnapshot],
    now: datetime | None = None,
) -> list[MemorySnapshot]:
    reference_time = now or datetime.now(UTC)
    active: list[MemorySnapshot] = []
    for snapshot in snapshots:
        if not _is_snapshot_active(snapshot.created_at, reference_time, int(snapshot.ttl_days)):
            continue
        active.append(snapshot)
    active.sort(key=lambda snapshot: snapshot.weight, reverse=True)
    return active


def _is_snapshot_active(created_at_raw: str, now: datetime, ttl_days: int) -> bool:
    try:
        created_at = datetime.fromisoformat(created_at_raw)
    except ValueError:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return now - created_at <= timedelta(days=max(ttl_days, 0))


def _default_profile(user_id: str) -> UserMemoryProfile:
    return UserMemoryProfile(
        user_id=_sanitize_user_id(user_id),
        constraints=UserMemoryConstraints(),
        long_term_preferences={
            "preferred_categories": {},
            "preferred_tags": {},
            "price_sensitivity": None,
        },
        interaction_preferences=UserMemoryInteractionPreferences(),
        governance={},
        source_events=[],
    )


def _normalize_profile(profile: UserMemoryProfile) -> UserMemoryProfile:
    profile.constraints.allergies = _unique_lower_trimmed(profile.constraints.allergies)
    profile.constraints.avoid_terms = _unique_lower_trimmed(profile.constraints.avoid_terms)
    profile.constraints.brand_exclude = _unique_lower_trimmed(profile.constraints.brand_exclude)
    profile.constraints.accessibility_needs = _unique_lower_trimmed(profile.constraints.accessibility_needs)
    profile.interaction_preferences.tone = profile.interaction_preferences.tone.strip() or "natural"
    profile.updated_at = profile.updated_at or _utc_now_iso()
    profile.source_events = [
        _normalize_source_event(event)
        for event in profile.source_events
        if event.event_type and event.event_value
    ]
    return profile


def _normalize_source_event(event: MemorySourceEvent) -> MemorySourceEvent:
    event.created_at = event.created_at or _utc_now_iso()
    event.source = event.source or None
    return event


def _unique_lower_trimmed(values: list[str]) -> list[str]:
    seen: list[str] = []
    for raw_value in values:
        value = str(raw_value).strip().lower()
        if value and value not in seen:
            seen.append(value)
    return seen


def _sanitize_user_id(user_id: str) -> str:
    sanitized = re.sub(r"[^0-9a-zA-Z._-]+", "_", user_id.strip() or DEFAULT_MEMORY_USER_ID)
    return sanitized[:120] if sanitized else DEFAULT_MEMORY_USER_ID


def _write_profile(path: Path, profile: UserMemoryProfile) -> None:
    path.write_text(
        json.dumps(profile.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
