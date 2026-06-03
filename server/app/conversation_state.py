import re
from dataclasses import dataclass, field

from app.models import ChatRequest, QueryIntent
from app.retrieval import parse_query_intent


CATEGORY_LABELS = {
    "beauty": "美妆护肤",
    "apparel": "服饰运动",
}

FACET_LABELS = {
    "skin_type": "肤质",
    "effect": "功效",
    "use_case": "场景",
    "sub_category": "子类",
}

FOLLOW_UP_TERMS = [
    "放宽",
    "降低",
    "降到",
    "降至",
    "先看",
    "先不看",
    "优先",
    "排除",
    "避开",
    "条件",
    "更",
    "便宜",
    "贵",
    "换",
    "改",
    "那",
    "它",
    "这个",
    "刚才",
    "上一款",
    "第一款",
    "第二款",
    "第三款",
]

CONTINUATION_MARKERS = [
    "还有",
    "另外",
    "补充",
    "其实",
    "也",
    "最好",
    "顺便",
]


@dataclass
class RuleConversationState:
    category_candidates: list[str] = field(default_factory=list)
    referenced_product_ids: list[str] = field(default_factory=list)
    budget_max: float | None = None
    budget_relaxed: bool = False
    facets: dict[str, list[str]] = field(default_factory=dict)
    exclude_terms: list[str] = field(default_factory=list)
    soft_preferences: list[str] = field(default_factory=list)
    comparison_mode: bool = False
    applied_messages: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass
class RetrievalMessageBuildResult:
    message: str
    applied: bool
    trace: dict


def build_retrieval_message(request: ChatRequest) -> RetrievalMessageBuildResult:
    previous_user_messages = [
        item.content.strip()
        for item in request.history
        if item.role == "user" and item.content.strip()
    ]
    current_message = request.message.strip()
    if not previous_user_messages:
        return RetrievalMessageBuildResult(
            message=current_message,
            applied=False,
            trace={"applied": False, "reason": "no_history"},
        )

    current_intent = parse_query_intent(current_message)
    if not _is_follow_up(current_message, current_intent):
        return RetrievalMessageBuildResult(
            message=current_message,
            applied=False,
            trace={"applied": False, "reason": "current_turn_is_self_contained"},
        )

    state = RuleConversationState()
    for message in previous_user_messages[-4:]:
        _merge_message(state, message, source="history")
    _merge_message(state, current_message, source="current")
    referenced_product_ids = _referenced_history_product_ids(current_message, request.history)
    if referenced_product_ids:
        state.referenced_product_ids = referenced_product_ids
        state.actions.append(f"current:reference_products={','.join(referenced_product_ids)}")

    merged_message = _format_merged_message(
        state=state,
        current_message=current_message,
    )
    return RetrievalMessageBuildResult(
        message=merged_message,
        applied=True,
        trace={
            "applied": True,
            "reason": "rule_only_state_merge",
            "source_user_turns": len(previous_user_messages[-4:]) + 1,
            "state": _state_trace(state),
        },
    )


def _is_follow_up(message: str, intent: QueryIntent) -> bool:
    normalized = message.strip()
    if len(normalized) <= 24:
        return True
    if _has_continuation_marker(normalized):
        return True
    has_structured_intent = (
        bool(intent.category_candidates)
        or bool(intent.facets)
        or intent.universal_constraints.budget_max is not None
        or bool(intent.exclude_terms)
    )
    if has_structured_intent and not any(term in normalized for term in FOLLOW_UP_TERMS):
        return False
    if any(term in normalized for term in FOLLOW_UP_TERMS):
        return True
    return not has_structured_intent


def _has_continuation_marker(message: str) -> bool:
    prefix = message[:18]
    if any(prefix.startswith(marker) for marker in CONTINUATION_MARKERS):
        return True
    return any(marker in prefix for marker in ["还有", "另外", "补充", "也最好", "最好", "顺便"])


def _merge_message(state: RuleConversationState, message: str, source: str) -> None:
    intent = parse_query_intent(message)
    state.applied_messages.append(message)
    subcategory_shift = bool(intent.facets.get("sub_category")) and _looks_like_subcategory_switch(message)

    if _relaxes_budget_without_value(message, intent):
        state.budget_max = None
        state.budget_relaxed = True
        state.actions.append(f"{source}:relax_budget")
    elif intent.universal_constraints.budget_max is not None:
        state.budget_max = intent.universal_constraints.budget_max
        state.budget_relaxed = False
        state.actions.append(f"{source}:set_budget={state.budget_max:g}")

    if _relaxes_exclusions_without_new_terms(message, intent):
        state.exclude_terms = []
        state.actions.append(f"{source}:relax_exclusions")
    elif intent.exclude_terms:
        _append_unique(state.exclude_terms, intent.exclude_terms)
        state.actions.append(f"{source}:keep_exclusions={','.join(intent.exclude_terms)}")

    if intent.category_candidates:
        if _should_replace_category(state.category_candidates, intent.category_candidates, message):
            state.category_candidates = list(intent.category_candidates)
            state.actions.append(f"{source}:replace_category={','.join(intent.category_candidates)}")
        else:
            _append_unique(state.category_candidates, intent.category_candidates)
            state.actions.append(f"{source}:merge_category={','.join(intent.category_candidates)}")

    for facet_name, values in intent.facets.items():
        if facet_name == "sub_category" and values and subcategory_shift:
            state.facets[facet_name] = list(values)
            state.actions.append(f"{source}:replace_sub_category={','.join(values)}")
        elif facet_name == "effect" and values and subcategory_shift:
            state.facets[facet_name] = list(values)
            state.actions.append(f"{source}:replace_effect={','.join(values)}")
        else:
            bucket = state.facets.setdefault(facet_name, [])
            _append_unique(bucket, values)
            state.actions.append(f"{source}:merge_{facet_name}={','.join(values)}")

    if intent.soft_preferences:
        _append_unique(state.soft_preferences, intent.soft_preferences)
    state.comparison_mode = state.comparison_mode or intent.comparison_mode


def _relaxes_budget_without_value(message: str, intent: QueryIntent) -> bool:
    if intent.universal_constraints.budget_max is not None:
        return False
    return bool(
        re.search(
            r"(放宽|不限制|不限|先不看|先不用管|可以超过).{0,8}(预算|价格|价位)",
            message,
        )
        or re.search(
            r"(预算|价格|价位).{0,8}(放宽|不限制|不限|先不看|先不用管|可以超过)",
            message,
        )
    )


def _relaxes_exclusions_without_new_terms(message: str, intent: QueryIntent) -> bool:
    if intent.exclude_terms:
        return False
    return bool(
        re.search(
            r"(放宽|先不看|先不用管|可以接受).{0,8}(排除|避开|酒精|刺激|成分)",
            message,
        )
        or re.search(
            r"(排除|避开|酒精|刺激|成分).{0,8}(放宽|先不看|先不用管|可以接受)",
            message,
        )
    )


def _should_replace_category(existing: list[str], incoming: list[str], message: str) -> bool:
    if not existing:
        return True
    if set(existing) == set(incoming):
        return False
    return any(term in message for term in ["换成", "换到", "改看", "重新看", "另一个品类"])


def _looks_like_subcategory_switch(message: str) -> bool:
    return any(term in message for term in ["换成", "换到", "改看", "先看", "只看", "重新看", "更偏", "有没有"])


def _format_merged_message(
    state: RuleConversationState,
    current_message: str,
) -> str:
    lines = ["规则合并后的检索状态："]
    if state.category_candidates:
        labels = [CATEGORY_LABELS.get(category, category) for category in state.category_candidates]
        lines.append(f"- 类目：{'、'.join(labels)}")
    if state.referenced_product_ids:
        lines.append(f"- 指代商品ID：{'、'.join(state.referenced_product_ids)}")
    for facet_name in ["skin_type", "effect", "use_case", "sub_category"]:
        values = state.facets.get(facet_name, [])
        if values:
            lines.append(f"- {FACET_LABELS.get(facet_name, facet_name)}：{'、'.join(values)}")
    if state.budget_max is not None:
        lines.append(f"- 预算：{state.budget_max:g}元以内")
    elif state.budget_relaxed:
        lines.append("- 预算：不限制")
    if state.exclude_terms:
        lines.append(f"- 排除：不要{'、'.join(state.exclude_terms)}")
    if state.soft_preferences:
        lines.append(f"- 偏好：{'、'.join(state.soft_preferences)}")
    if state.comparison_mode:
        lines.append("- 意图：对比/选择")

    return "\n".join(
        [
            *lines,
            "本轮补充：",
            current_message,
        ]
    )


def _state_trace(state: RuleConversationState) -> dict:
    return {
        "category_candidates": state.category_candidates,
        "referenced_product_ids": state.referenced_product_ids,
        "budget_max": state.budget_max,
        "budget_relaxed": state.budget_relaxed,
        "facets": state.facets,
        "exclude_terms": state.exclude_terms,
        "soft_preferences": state.soft_preferences,
        "comparison_mode": state.comparison_mode,
        "actions": state.actions,
    }


def _append_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _referenced_history_product_ids(message: str, history: list) -> list[str]:
    product_ids = _latest_history_product_ids(history)
    if not product_ids:
        return []
    index = _referenced_product_index(message)
    if index is None:
        return []
    if index >= len(product_ids):
        return []
    return [product_ids[index]]


def _latest_history_product_ids(history: list) -> list[str]:
    for item in reversed(history):
        if item.role != "assistant":
            continue
        product_ids = [product_id for product_id in item.product_ids if product_id]
        if product_ids:
            return product_ids
    return []


def _referenced_product_index(message: str) -> int | None:
    normalized = message.strip()
    explicit_patterns = [
        (r"(第一|第1(?:个|款|件)?|1(?:号|个|款|件))", 0),
        (r"(第二|第2(?:个|款|件)?|2(?:号|个|款|件))", 1),
        (r"(第三|第3(?:个|款|件)?|3(?:号|个|款|件))", 2),
    ]
    for pattern, index in explicit_patterns:
        if re.search(pattern, normalized):
            return index
    if any(term in normalized for term in ["它", "这个", "这款", "刚才那个", "刚才那款", "上一款", "上一个"]):
        return 0
    return None
