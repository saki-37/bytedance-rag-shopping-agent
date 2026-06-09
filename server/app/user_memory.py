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
    RecipientProfile,
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


def resolve_recipient_profile(
    memory_profile: UserMemoryProfile,
    recipient_id: str | None = None,
) -> RecipientProfile:
    target_id = (recipient_id or memory_profile.selected_recipient_id or "self").strip() or "self"
    for recipient in memory_profile.recipients:
        if recipient.recipient_id == target_id:
            return recipient
    return _ensure_self_recipient(memory_profile)


def build_memory_augmented_request(
    request: ChatRequest,
    memory_profile: UserMemoryProfile,
    recipient_profile: RecipientProfile | None = None,
) -> tuple[ChatRequest, list[str], dict[str, object], list[str]]:
    now = datetime.now(UTC)
    resolved_recipient = recipient_profile or resolve_recipient_profile(memory_profile, request.recipient_id)
    context_lines = memory_context_lines(memory_profile, recipient_profile=resolved_recipient, now=now)
    if not context_lines:
        return request, [], {}, []

    prefix = "历史记忆约束（不直接向用户暴露）：\n" + "\n".join(context_lines) + "\n\n"
    augmented_message = f"{prefix}{request.message}"
    applied_constraints = _collect_applied_constraints(memory_profile, recipient_profile=resolved_recipient)
    applied_short_term_signals = _collect_applied_short_term_signals(memory_profile, now=now)
    request = request.model_copy(update={"recipient_id": resolved_recipient.recipient_id})
    return (
        request.model_copy(update={"message": augmented_message}),
        context_lines,
        applied_constraints,
        applied_short_term_signals,
    )


def memory_context_lines(
    memory_profile: UserMemoryProfile,
    now: datetime | None = None,
    recipient_profile: RecipientProfile | None = None,
) -> list[str]:
    reference_time = now or datetime.now(UTC)
    recipient = recipient_profile or resolve_recipient_profile(memory_profile)
    lines: list[str] = []
    constraints = recipient.constraints
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
    if recipient.relationship:
        lines.append(f"- 当前对象关系：{recipient.relationship}")
    if recipient.body_profile.skin_type:
        lines.append(f"- 皮肤类型：{recipient.body_profile.skin_type}")
    if recipient.body_profile.shoe_size:
        lines.append(f"- 鞋码：{recipient.body_profile.shoe_size}")
    if recipient.body_profile.clothing_size:
        lines.append(f"- 衣码：{recipient.body_profile.clothing_size}")
    if recipient.shipping.address_label or recipient.shipping.address:
        lines.append("- 当前对象已配置收货地址")
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
    recipient_profile: RecipientProfile | None = None,
    fallback: str | None = None,
) -> MemoryTrace:
    resolved_recipient = recipient_profile or resolve_recipient_profile(memory_profile)
    return MemoryTrace(
        provider=provider,
        user_id=user_id,
        enabled=provider != MEMORY_PROVIDER_DISABLED,
        selected_recipient_id=resolved_recipient.recipient_id,
        recipient_memory_trace=_recipient_memory_trace(resolved_recipient),
        applied_constraints=applied_constraints,
        applied_short_term_signals=applied_short_term_signals,
        applied_preferences=applied_preferences,
        skipped_items=skipped,
        fallback=fallback,
    )


def _collect_applied_constraints(
    memory_profile: UserMemoryProfile,
    recipient_profile: RecipientProfile | None = None,
) -> dict[str, object]:
    recipient = recipient_profile or resolve_recipient_profile(memory_profile)
    constraints = recipient.constraints
    return {
        "constraints": {
            "allergies": constraints.allergies,
            "avoid_terms": constraints.avoid_terms,
            "brand_exclude": constraints.brand_exclude,
            "budget_max": constraints.budget_max,
            "accessibility_needs": constraints.accessibility_needs,
        },
        "long_term_preferences": {
            "preferred_categories": recipient.long_term_preferences.preferred_categories,
            "preferred_tags": recipient.long_term_preferences.preferred_tags,
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
    base_constraints = UserMemoryConstraints()
    base_preferences = {
        "preferred_categories": {},
        "preferred_tags": {},
        "price_sensitivity": None,
    }
    return UserMemoryProfile(
        user_id=_sanitize_user_id(user_id),
        constraints=base_constraints,
        long_term_preferences=base_preferences,
        recipients=[
            _build_recipient_profile(
                recipient_id="self",
                display_name="自己",
                relationship="self",
                constraints=base_constraints,
                long_term_preferences=base_preferences,
            )
        ],
        selected_recipient_id="self",
        interaction_preferences=UserMemoryInteractionPreferences(),
        governance={},
        source_events=[],
    )


def _normalize_profile(profile: UserMemoryProfile) -> UserMemoryProfile:
    profile.user_id = _sanitize_user_id(profile.user_id)
    profile.constraints.allergies = _unique_lower_trimmed(profile.constraints.allergies)
    profile.constraints.avoid_terms = _unique_lower_trimmed(profile.constraints.avoid_terms)
    profile.constraints.brand_exclude = _unique_lower_trimmed(profile.constraints.brand_exclude)
    profile.constraints.accessibility_needs = _unique_lower_trimmed(profile.constraints.accessibility_needs)
    profile.interaction_preferences.tone = profile.interaction_preferences.tone.strip() or "natural"
    profile.recipients = _normalize_recipients(profile)
    profile.selected_recipient_id = profile.selected_recipient_id.strip() or "self"
    if profile.selected_recipient_id not in {recipient.recipient_id for recipient in profile.recipients}:
        profile.selected_recipient_id = profile.recipients[0].recipient_id
    profile.updated_at = profile.updated_at or _utc_now_iso()
    profile.source_events = [
        _normalize_source_event(event)
        for event in profile.source_events
        if event.event_type and event.event_value
    ]
    return profile


def _normalize_recipients(profile: UserMemoryProfile) -> list[RecipientProfile]:
    recipients: list[RecipientProfile] = []
    seen: set[str] = set()
    for recipient in profile.recipients:
        normalized = _normalize_recipient_profile(recipient)
        if normalized.recipient_id in seen:
            continue
        recipients.append(normalized)
        seen.add(normalized.recipient_id)

    if "self" not in seen:
        recipients.insert(
            0,
            _build_recipient_profile(
                recipient_id="self",
                display_name="自己",
                relationship="self",
                constraints=profile.constraints,
                long_term_preferences=profile.long_term_preferences,
            ),
        )
    return recipients


def _normalize_recipient_profile(recipient: RecipientProfile) -> RecipientProfile:
    recipient.recipient_id = recipient.recipient_id.strip() or f"custom-{_utc_now_iso()}"
    recipient.display_name = recipient.display_name.strip() or recipient.recipient_id
    recipient.relationship = recipient.relationship.strip() if recipient.relationship else None
    recipient.constraints.allergies = _unique_lower_trimmed(recipient.constraints.allergies)
    recipient.constraints.avoid_terms = _unique_lower_trimmed(recipient.constraints.avoid_terms)
    recipient.constraints.brand_exclude = _unique_lower_trimmed(recipient.constraints.brand_exclude)
    recipient.constraints.accessibility_needs = _unique_lower_trimmed(recipient.constraints.accessibility_needs)
    if recipient.shipping is None:
        recipient.shipping = recipient.shipping.__class__()
    if recipient.body_profile is None:
        recipient.body_profile = recipient.body_profile.__class__()
    if recipient.long_term_preferences is None:
        recipient.long_term_preferences = recipient.long_term_preferences.__class__()
    recipient.updated_at = recipient.updated_at or _utc_now_iso()
    return recipient


def _build_recipient_profile(
    recipient_id: str,
    display_name: str,
    relationship: str | None,
    constraints: UserMemoryConstraints,
    long_term_preferences: dict[str, object],
) -> RecipientProfile:
    return RecipientProfile(
        recipient_id=recipient_id,
        display_name=display_name,
        relationship=relationship,
        constraints=constraints,
        long_term_preferences=long_term_preferences,
        updated_at=_utc_now_iso(),
    )


def _ensure_self_recipient(memory_profile: UserMemoryProfile) -> RecipientProfile:
    return _build_recipient_profile(
        recipient_id="self",
        display_name="自己",
        relationship="self",
        constraints=memory_profile.constraints,
        long_term_preferences=memory_profile.long_term_preferences,
    )


def _recipient_memory_trace(recipient_profile: RecipientProfile) -> dict[str, object]:
    return {
        "recipient_id": recipient_profile.recipient_id,
        "display_name": recipient_profile.display_name,
        "relationship": recipient_profile.relationship,
        "applied_constraints": {
            "allergies": bool(recipient_profile.constraints.allergies),
            "avoid_terms": bool(recipient_profile.constraints.avoid_terms),
            "brand_exclude": bool(recipient_profile.constraints.brand_exclude),
            "budget_max": recipient_profile.constraints.budget_max,
        },
        "applied_preferences": {
            "preferred_categories": len(recipient_profile.long_term_preferences.preferred_categories),
            "preferred_tags": len(recipient_profile.long_term_preferences.preferred_tags),
        },
        "applied_profile_fields": {
            "has_body_profile": bool(
                recipient_profile.body_profile.skin_type
                or recipient_profile.body_profile.shoe_size
                or recipient_profile.body_profile.clothing_size,
            ),
            "has_shipping": bool(
                recipient_profile.shipping.address_label
                or recipient_profile.shipping.recipient_name
                or recipient_profile.shipping.phone
                or recipient_profile.shipping.address
            ),
        },
    }


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
