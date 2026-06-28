"""多轮对话状态与约束继承（规则层，不依赖 LLM）。

核心职责：把"帮我推荐跑鞋 -> 要轻量的 -> 预算 500 以内"这类多轮追问，
合并成一条带完整约束的检索消息（retrieval message），供下游 RAG 使用。

设计要点：
1. 先判断本轮是不是追问（_is_follow_up）：自包含的新需求不继承历史，
   避免上一轮的预算/类目污染新话题。
2. 是追问时，把最近最多 4 轮用户消息逐条合并进 RuleConversationState，
   预算取最新值、排除词累加、放宽语义（"贵一点也行"）会显式清除旧约束。
3. "第一款 / 它 / 刚才那款"等商品指代通过 history 里 assistant 带回的
   product_ids 解析成具体 product_id（_referenced_history_product_ids）。
4. 全程产出 constraint_trace（本轮/继承/放宽/生效），写入 RetrievalTrace
   供调试与答辩复验，证明约束确实被继承而不是模型猜的。
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.constraint_state import is_constraint_removed
from app.models import ChatRequest, ConstraintOverrideSnapshot, QueryIntent
from app.data_loader import load_raw_products
from app.retrieval import CATEGORY_TO_RAW, FACET_LEXICON, RAW_TO_CATEGORY, category_exclusions, parse_query_intent


CATEGORY_LABELS = CATEGORY_TO_RAW

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

FOLLOW_UP_ONLY_TERMS = [
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
    "便宜",
    "贵",
    "换成",
    "换到",
    "改看",
    "刚才",
    "上一款",
    "第一款",
    "第二款",
    "第三款",
    "那款",
    "这款",
    "那个",
    "这个",
    "它",
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
    """跨轮累积的结构化约束。actions 记录每条约束的来源（history/current），用于 trace。"""

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
    """规则版多轮合并入口：自包含查询原样返回；追问则合并历史约束后重写检索消息。"""
    previous_user_messages = [
        item.content.strip()
        for item in request.history
        if item.role == "user" and item.content.strip()
    ]
    current_message = request.message.strip()
    current_intent = parse_query_intent(current_message)
    referenced_product_ids = _referenced_history_product_ids(current_message, request.history)
    if not previous_user_messages:
        if referenced_product_ids:
            state = RuleConversationState()
            _merge_message(state, current_message, source="current")
            _apply_referenced_products(state, referenced_product_ids, source="current")
            _apply_constraint_overrides_to_state(state, request.constraint_overrides)
            return RetrievalMessageBuildResult(
                message=_format_merged_message(state=state, current_message=current_message),
                applied=True,
                trace={
                    "applied": True,
                    "reason": "assistant_card_reference_only",
                    "source_user_turns": 1,
                    "state": _state_trace(state),
                    "constraint_trace": _constraint_trace_from_state(state),
                },
            )
        return RetrievalMessageBuildResult(
            message=current_message,
            applied=False,
            trace={
                "applied": False,
                "reason": "no_history",
                "constraint_trace": _constraint_trace_from_intent(current_intent),
            },
        )

    if not referenced_product_ids and not _is_follow_up(current_message, current_intent):
        return RetrievalMessageBuildResult(
            message=current_message,
            applied=False,
            trace={
                "applied": False,
                "reason": "current_turn_is_self_contained",
                "constraint_trace": _constraint_trace_from_intent(current_intent),
            },
        )

    state = RuleConversationState()
    for message in previous_user_messages[-4:]:
        _merge_message(state, message, source="history")
    _merge_message(state, current_message, source="current")
    if referenced_product_ids:
        _apply_referenced_products(state, referenced_product_ids, source="current")
    else:
        _inherit_active_product_context(state, request.history)
    _apply_constraint_overrides_to_state(state, request.constraint_overrides)

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
            "constraint_trace": _constraint_trace_from_state(state),
        },
    )


def _is_follow_up(message: str, intent: QueryIntent) -> bool:
    normalized = message.strip()
    if category_exclusions(normalized):
        return True
    if _has_continuation_marker(normalized):
        return True
    if _is_self_contained_domain_query(normalized, intent):
        return False
    if _is_self_contained_clarification_query(normalized, intent):
        return False
    if len(normalized) <= 24:
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


def _is_self_contained_domain_query(message: str, intent: QueryIntent) -> bool:
    has_domain_intent = bool(intent.facets.get("sub_category")) or any(
        category != "beauty" for category in intent.category_candidates
    )
    if not has_domain_intent:
        return False
    if _has_product_reference_signal(message):
        return False
    return not _has_follow_up_only_term(message)


def _is_self_contained_clarification_query(message: str, intent: QueryIntent) -> bool:
    if not intent.needs_clarification:
        return False
    if not (intent.category_candidates or intent.facets):
        return False
    if _has_product_reference_signal(message):
        return False
    return not _has_follow_up_only_term(message)


def _has_follow_up_only_term(message: str) -> bool:
    return any(term in message for term in FOLLOW_UP_ONLY_TERMS)


def _has_continuation_marker(message: str) -> bool:
    prefix = message[:18]
    if any(prefix.startswith(marker) for marker in CONTINUATION_MARKERS):
        return True
    return any(marker in prefix for marker in ["还有", "另外", "补充", "也最好", "最好", "顺便"])


def _merge_message(state: RuleConversationState, message: str, source: str) -> None:
    intent = parse_query_intent(message)
    state.applied_messages.append(message)
    subcategory_shift = bool(intent.facets.get("sub_category")) and _looks_like_subcategory_switch(message)
    excluded_categories = category_exclusions(message)

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

    if excluded_categories:
        before = list(state.category_candidates)
        state.category_candidates = [
            category for category in state.category_candidates
            if category not in excluded_categories
        ]
        removed = [category for category in before if category in excluded_categories]
        if removed:
            state.actions.append(f"{source}:exclude_category={','.join(removed)}")
        if "beauty" in excluded_categories:
            _clear_beauty_specific_facets(state, source)

    if intent.category_candidates:
        if excluded_categories or _should_replace_category(state.category_candidates, intent.category_candidates, message):
            state.category_candidates = list(intent.category_candidates)
            state.actions.append(f"{source}:replace_category={','.join(intent.category_candidates)}")
            if "beauty" not in state.category_candidates:
                _clear_beauty_specific_facets(state, source)
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
    if source == "current":
        state.comparison_mode = intent.comparison_mode
        if intent.comparison_mode:
            state.actions.append(f"{source}:comparison_mode")


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


def _clear_beauty_specific_facets(state: RuleConversationState, source: str) -> None:
    removed: list[str] = []
    for facet_name in ["skin_type"]:
        if state.facets.pop(facet_name, None):
            removed.append(facet_name)
    if removed:
        state.actions.append(f"{source}:clear_beauty_facets={','.join(removed)}")


def _should_replace_category(existing: list[str], incoming: list[str], message: str) -> bool:
    if not existing:
        return True
    if set(existing) == set(incoming):
        return False
    return any(term in message for term in [
        "换成",
        "换到",
        "改看",
        "重新看",
        "另一个品类",
        "其他品类",
        "别的品类",
        "运动类",
        "运动用品",
        "非化妆品",
        "非美妆",
        "非护肤",
        "不是化妆品",
        "不要化妆品",
        "不看化妆品",
    ])


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


def _apply_referenced_products(state: RuleConversationState, product_ids: list[str], source: str) -> None:
    state.referenced_product_ids = product_ids
    state.actions.append(f"{source}:reference_products={','.join(product_ids)}")
    _apply_product_context(state, product_ids, source=source, replace_existing=True)


def _inherit_active_product_context(state: RuleConversationState, history: list) -> None:
    if state.facets.get("sub_category"):
        return
    product_ids = _latest_history_product_ids(history)
    if not product_ids:
        return
    context = _product_context_for_product_ids(product_ids)
    if not _is_coherent_product_context(product_ids, context):
        return
    _apply_product_context(state, product_ids, source="history", replace_existing=False)


def _apply_product_context(
    state: RuleConversationState,
    product_ids: list[str],
    *,
    source: str,
    replace_existing: bool,
) -> None:
    context = _product_context_for_product_ids(product_ids)
    categories = context["categories"]
    sub_categories = context["sub_categories"]
    effects = context["effects"]

    if categories:
        before = list(state.category_candidates)
        if replace_existing and not state.category_candidates:
            state.category_candidates = list(categories)
        elif not state.category_candidates:
            _append_unique(state.category_candidates, categories)
        else:
            _append_unique(state.category_candidates, [
                category for category in categories if category in state.category_candidates
            ])
        if state.category_candidates != before:
            state.actions.append(f"{source}:merge_category={','.join(state.category_candidates)}")

    if sub_categories and (replace_existing or not state.facets.get("sub_category")):
        state.facets["sub_category"] = list(sub_categories)
        state.actions.append(f"{source}:merge_sub_category={','.join(sub_categories)}")
    if effects and not state.facets.get("effect"):
        state.facets["effect"] = list(effects)
        state.actions.append(f"{source}:merge_effect={','.join(effects)}")


def _product_context_for_product_ids(product_ids: list[str]) -> dict[str, list[str]]:
    products = _raw_products_by_id()
    categories: list[str] = []
    sub_categories: list[str] = []
    for product_id in product_ids:
        raw = products.get(product_id)
        if not raw:
            continue
        raw_category = str(raw.get("category", "")).strip()
        category = RAW_TO_CATEGORY.get(raw_category)
        if category and category not in categories:
            categories.append(category)
        sub_category = str(raw.get("sub_category", "")).strip()
        if sub_category and sub_category not in sub_categories:
            sub_categories.append(sub_category)
    effects = [
        sub_category
        for sub_category in sub_categories
        if sub_category in FACET_LEXICON.get("effect", {})
    ]
    return {
        "categories": categories,
        "sub_categories": sub_categories,
        "effects": effects,
    }


def _is_coherent_product_context(product_ids: list[str], context: dict[str, list[str]]) -> bool:
    if len(product_ids) == 1:
        return True
    categories = context.get("categories", [])
    sub_categories = context.get("sub_categories", [])
    return len(categories) == 1 and len(sub_categories) == 1


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


def _constraint_trace_from_intent(intent: QueryIntent) -> dict:
    current_turn = _constraints_from_intent(intent)
    return {
        "current_turn": current_turn,
        "inherited": {},
        "relaxed": [],
        "effective": current_turn,
        "actions": [],
    }


def _constraint_trace_from_state(state: RuleConversationState) -> dict:
    current_actions = [action for action in state.actions if action.startswith("current:")]
    history_actions = [action for action in state.actions if action.startswith("history:")]
    current_turn = _constraints_from_actions(current_actions)
    inherited = _constraints_from_actions(history_actions)
    relaxed = _relaxed_constraints_from_actions(current_actions)
    if _budget_was_relaxed(current_turn, inherited) and "budget_max" not in relaxed:
        relaxed.append("budget_max")
    return {
        "current_turn": current_turn,
        "inherited": inherited,
        "relaxed": relaxed,
        "effective": _effective_constraints_from_state(state),
        "actions": state.actions,
    }


def _apply_constraint_overrides_to_state(
    state: RuleConversationState,
    overrides: ConstraintOverrideSnapshot | None,
) -> None:
    if overrides is None or not overrides.removed_constraint_ids:
        return
    current_constraints = _constraints_from_actions([
        action for action in state.actions if action.startswith("current:")
    ])

    current_budget = current_constraints.get("budget_max")
    if (
        state.budget_max is not None
        and current_budget is None
        and is_constraint_removed(overrides, "budget_max", state.budget_max)
    ):
        removed_budget = state.budget_max
        state.budget_max = None
        state.budget_relaxed = True
        state.actions.append(f"override:remove_budget={removed_budget:g}")

    current_exclusions = set(current_constraints.get("exclude_terms", []))
    retained_exclusions: list[str] = []
    removed_exclusions: list[str] = []
    for term in state.exclude_terms:
        if term in current_exclusions or not is_constraint_removed(overrides, "exclude_terms", term):
            retained_exclusions.append(term)
        else:
            removed_exclusions.append(term)
    if removed_exclusions:
        state.exclude_terms = retained_exclusions
        state.actions.append(f"override:remove_exclusions={','.join(removed_exclusions)}")


def _constraints_from_intent(intent: QueryIntent) -> dict[str, object]:
    constraints: dict[str, object] = {}
    if intent.category_candidates:
        constraints["category_candidates"] = intent.category_candidates
    if intent.referenced_product_ids:
        constraints["referenced_product_ids"] = intent.referenced_product_ids
    if intent.universal_constraints.budget_max is not None:
        constraints["budget_max"] = intent.universal_constraints.budget_max
    if intent.universal_constraints.brand_exclude:
        constraints["brand_exclude"] = intent.universal_constraints.brand_exclude
    if intent.facets:
        constraints["facets"] = intent.facets
    if intent.exclude_terms:
        constraints["exclude_terms"] = intent.exclude_terms
    if intent.soft_preferences:
        constraints["soft_preferences"] = intent.soft_preferences
    if intent.comparison_mode:
        constraints["comparison_mode"] = True
    return constraints


def _constraints_from_actions(actions: list[str]) -> dict[str, object]:
    constraints: dict[str, object] = {}
    facets: dict[str, list[str]] = {}
    for action in actions:
        body = action.split(":", 1)[1] if ":" in action else action
        if body.startswith("set_budget="):
            constraints["budget_max"] = _parse_float(body.removeprefix("set_budget="))
        elif body == "relax_budget":
            constraints["budget_relaxed"] = True
        elif body == "relax_exclusions":
            constraints["exclude_terms_relaxed"] = True
        elif body.startswith("keep_exclusions="):
            _merge_constraint_values(constraints, "exclude_terms", body.removeprefix("keep_exclusions="))
        elif body.startswith("reference_products="):
            _merge_constraint_values(constraints, "referenced_product_ids", body.removeprefix("reference_products="))
        elif body == "comparison_mode":
            constraints["comparison_mode"] = True
        elif body.startswith(("replace_category=", "merge_category=")):
            values = body.split("=", 1)[1]
            _merge_constraint_values(constraints, "category_candidates", values)
        elif body.startswith("replace_sub_category="):
            facets["sub_category"] = _split_action_values(body.split("=", 1)[1])
        elif body.startswith("replace_effect="):
            facets["effect"] = _split_action_values(body.split("=", 1)[1])
        elif body.startswith("merge_") and "=" in body:
            facet_name, values = body.split("=", 1)
            facet_name = facet_name.removeprefix("merge_")
            if facet_name in FACET_LABELS:
                bucket = facets.setdefault(facet_name, [])
                _append_unique(bucket, _split_action_values(values))
    if facets:
        constraints["facets"] = facets
    return {key: value for key, value in constraints.items() if value not in (None, [], {})}


def _relaxed_constraints_from_actions(actions: list[str]) -> list[str]:
    relaxed: list[str] = []
    if any(action.endswith(":relax_budget") for action in actions):
        relaxed.append("budget_max")
    if any(action.endswith(":relax_exclusions") for action in actions):
        relaxed.append("exclude_terms")
    return relaxed


def _budget_was_relaxed(current_turn: dict[str, object], inherited: dict[str, object]) -> bool:
    current_budget = current_turn.get("budget_max")
    inherited_budget = inherited.get("budget_max")
    if not isinstance(current_budget, (int, float)) or not isinstance(inherited_budget, (int, float)):
        return False
    return float(current_budget) > float(inherited_budget)


def _effective_constraints_from_state(state: RuleConversationState) -> dict[str, object]:
    constraints: dict[str, object] = {}
    if state.category_candidates:
        constraints["category_candidates"] = state.category_candidates
    if state.referenced_product_ids:
        constraints["referenced_product_ids"] = state.referenced_product_ids
    if state.budget_max is not None:
        constraints["budget_max"] = state.budget_max
    elif state.budget_relaxed:
        constraints["budget_relaxed"] = True
    if state.facets:
        constraints["facets"] = state.facets
    if state.exclude_terms:
        constraints["exclude_terms"] = state.exclude_terms
    if state.soft_preferences:
        constraints["soft_preferences"] = state.soft_preferences
    if state.comparison_mode:
        constraints["comparison_mode"] = True
    return constraints


def _merge_constraint_values(constraints: dict[str, object], key: str, raw_values: str) -> None:
    values = _split_action_values(raw_values)
    existing = constraints.setdefault(key, [])
    if isinstance(existing, list):
        _append_unique(existing, values)


def _split_action_values(raw_values: str) -> list[str]:
    return [value for value in raw_values.split(",") if value]


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _append_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _referenced_history_product_ids(message: str, history: list) -> list[str]:
    active_product_ids = _latest_history_product_ids(history)
    if not active_product_ids:
        return []
    if _references_first_two_products(message):
        return active_product_ids[:2]
    indexes = _referenced_product_indexes(message)
    if indexes:
        return [active_product_ids[index] for index in indexes if index < len(active_product_ids)]
    if _references_all_previous_products(message):
        return active_product_ids
    mentioned_ids = _mentioned_history_product_ids(message, active_product_ids)
    if mentioned_ids:
        return mentioned_ids
    recent_mentioned_ids = _mentioned_history_product_ids(message, _recent_history_product_ids(history))
    if recent_mentioned_ids:
        return recent_mentioned_ids
    if _references_single_active_product(message, active_product_ids):
        return active_product_ids
    index = _referenced_product_index(message)
    if index is None:
        return []
    if index >= len(active_product_ids):
        return []
    return [active_product_ids[index]]


def _mentioned_history_product_ids(message: str, product_ids: list[str]) -> list[str]:
    normalized_message = _normalize_reference_text(message)
    if not normalized_message:
        return []
    if _requests_more_or_alternative(normalized_message):
        return []

    products = _raw_products_by_id()
    matched: list[str] = []
    for product_id in product_ids:
        raw = products.get(product_id)
        if not raw:
            continue
        strong_aliases, context_aliases = _history_product_aliases(raw)
        strong_match = any(alias and alias in normalized_message for alias in strong_aliases)
        context_match = _has_product_reference_signal(message) and any(
            alias and alias in normalized_message for alias in context_aliases
        )
        if strong_match or context_match:
            matched.append(product_id)
    return matched if len(matched) == 1 else []


def _references_single_active_product(message: str, active_product_ids: list[str]) -> bool:
    if len(active_product_ids) != 1:
        return False
    normalized_message = _normalize_reference_text(message)
    if _requests_more_or_alternative(normalized_message):
        return False
    return any(
        signal in normalized_message
        for signal in [
            "它",
            "这个",
            "这款",
            "那款",
            "刚才",
            "上一款",
            "多大",
            "多少码",
            "尺码",
            "怎么用",
            "适合吗",
            "合适吗",
        ]
    )


def _requests_more_or_alternative(normalized_message: str) -> bool:
    return any(term in normalized_message for term in ["别的", "其他", "更多", "还有没有", "换一", "换个"])


def _has_product_reference_signal(message: str) -> bool:
    normalized = message.strip()
    signals = [
        "前面",
        "之前",
        "刚才",
        "刚刚",
        "上面",
        "那个",
        "那条",
        "那件",
        "那双",
        "这条",
        "这件",
        "这双",
        "这款",
        "不错",
        "喜欢",
        "倾向",
        "也可以买",
        "也想",
        "也看",
        "呢",
        "多大",
        "多少码",
        "尺码",
        "合适",
    ]
    return any(signal in normalized for signal in signals)


@lru_cache(maxsize=1)
def _raw_products_by_id() -> dict[str, dict]:
    data_root = Path(__file__).resolve().parents[2] / "data" / "raw"
    raw_root = data_root / "ecommerce_agent_dataset"
    if not raw_root.exists():
        raw_root = data_root
    if not raw_root.exists():
        return {}
    return load_raw_products(raw_root)


def _history_product_aliases(raw: dict) -> tuple[list[str], list[str]]:
    brand = str(raw.get("brand", "")).strip()
    title = str(raw.get("title", "")).strip()
    sub_category = str(raw.get("sub_category", "")).strip()
    strong_aliases = {
        _normalize_reference_text(brand),
        _normalize_reference_text(title),
    }
    context_aliases = {_normalize_reference_text(sub_category)}
    sub_category_aliases = FACET_LEXICON.get("sub_category", {}).get(sub_category, [])
    context_aliases.update(_normalize_reference_text(alias) for alias in sub_category_aliases)
    # 口语化类型词：用户常说"那条裤子/那双鞋/那个帽子"，而 sub_category 是
    # "运动长裤/跑步鞋"等，子串匹配不到（真实 case：'之前的那条裤子'未解析到
    # 已推荐的长裤，导致候选混入卫衣）。按类型补口语别名；多个候选同型时
    # 仍受"恰好命中一个才生效"的保守规则保护。
    for type_char, spoken_alias in (("裤", "裤子"), ("鞋", "鞋子"), ("帽", "帽子")):
        if type_char in sub_category:
            context_aliases.add(spoken_alias)
    if any(marker in sub_category for marker in ["T恤", "卫衣"]) or "上衣" in title:
        context_aliases.update({"上衣", "衣服"})
    if brand == "阿迪达斯":
        strong_aliases.add("adidas")
    if brand == "安热沙":
        strong_aliases.add("安耐晒")
    if brand and title.startswith(brand):
        short_title = title[len(brand) : len(brand) + 8]
        strong_aliases.add(_normalize_reference_text(short_title))
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", title):
        strong_aliases.add(_normalize_reference_text(token))
    strong = [
        alias
        for alias in strong_aliases
        if len(alias) >= 3 and alias not in {"运动", "服饰", "商品", "推荐", "合适"}
    ]
    context = [
        alias
        for alias in context_aliases
        if len(alias) >= 2 and alias not in {"运动", "服饰", "商品", "推荐", "合适", "裤", "鞋", "衣"}
    ]
    return strong, context


def _normalize_reference_text(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _latest_history_product_ids(history: list) -> list[str]:
    for item in reversed(history):
        if item.role != "assistant":
            continue
        product_ids = [product_id for product_id in item.product_ids if product_id]
        if product_ids:
            return product_ids
    return []


def _recent_history_product_ids(history: list, max_assistant_turns: int = 6) -> list[str]:
    product_ids: list[str] = []
    assistant_turns = 0
    for item in reversed(history):
        if item.role != "assistant":
            continue
        assistant_turns += 1
        for product_id in item.product_ids:
            if product_id and product_id not in product_ids:
                product_ids.append(product_id)
        if assistant_turns >= max_assistant_turns:
            break
    return product_ids


def _referenced_product_index(message: str) -> int | None:
    normalized = message.strip()
    explicit_patterns = [
        (r"(第一|第1(?:个|款|件)?|1号)", 0),
        (r"(第二|第2(?:个|款|件)?|2号)", 1),
        (r"(第三|第3(?:个|款|件)?|3号)", 2),
    ]
    for pattern, index in explicit_patterns:
        if re.search(pattern, normalized):
            return index
    if any(term in normalized for term in ["它", "这款", "那款", "刚才那个", "刚才那款", "上一款", "上一个"]):
        return 0
    if _has_product_deictic_reference(normalized):
        return 0
    return None


def _referenced_product_indexes(message: str) -> list[int]:
    normalized = message.strip()
    markers = [
        (r"(第一|第1(?:个|款|件)?|1号)", 0),
        (r"(第二|第2(?:个|款|件)?|2号)", 1),
        (r"(第三|第3(?:个|款|件)?|3号)", 2),
    ]
    indexes = [index for pattern, index in markers if re.search(pattern, normalized)]
    if _has_numbered_comparison_context(normalized):
        indexes.extend(_numbered_pair_or_list_indexes(normalized))
    if indexes and any(term in normalized for term in ["它", "这款", "那款", "刚才那个", "刚才那款", "上一款", "上一个"]):
        indexes.insert(0, 0)
    return list(dict.fromkeys(indexes))


def _has_numbered_comparison_context(message: str) -> bool:
    return any(term in message for term in ["比较", "对比", "1和", "1 和", "一和", "一 和", "和2", "和 2", "和二", "和 二"])


def _numbered_pair_or_list_indexes(message: str) -> list[int]:
    token_to_index = {"1": 0, "一": 0, "2": 1, "二": 1, "3": 2, "三": 2}
    token = r"(?<!第)(?<!\d)[123一二三](?![\d个款件号套双])"
    separator = r"\s*(?:和|跟|与|及|、|,|，)\s*"
    indexes: list[int] = []
    for match in re.finditer(rf"{token}(?:{separator}{token})+", message):
        for raw_token in re.findall(r"[123一二三]", match.group(0)):
            indexes.append(token_to_index[raw_token])
    return list(dict.fromkeys(indexes))


def _has_product_deictic_reference(message: str) -> bool:
    return bool(
        re.search(r"(这个|那个|这一个|那一个).{0,4}(商品|产品|卡片|款|牌子|品牌)", message)
        or re.search(r"(商品|产品|卡片|款|牌子|品牌).{0,4}(这个|那个|这一个|那一个)", message)
    )


def _references_first_two_products(message: str) -> bool:
    return bool(re.search(r"(前两|前二|前2|前两个|前二个|前两款|前2款)", message))


def _references_all_previous_products(message: str) -> bool:
    normalized_message = re.sub(r"比较(合适|适合|舒服|稳妥|好|划算|便宜|贵|大|小)", "", message)
    if not any(term in normalized_message for term in ["对比", "比较", "怎么选", "哪个更", "哪款更", "区别"]):
        return False
    return any(term in normalized_message for term in [
        "这几个",
        "这些",
        "它们",
        "刚才这些",
        "刚才几个",
        "这三款",
        "这3款",
        "三款",
        "3款",
        "全部",
        "都",
    ])
