import asyncio
import json
import logging
import re
import time
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.conversation_state import RetrievalMessageBuildResult, build_retrieval_message
from app.models import ChatMessage, ChatRequest
from app.retrieval import CATEGORY_TO_RAW, EXCLUDE_TERMS, FACET_LEXICON, category_exclusions, parse_query_intent


logger = logging.getLogger(__name__)

CATEGORY_SIGNAL_ALIASES = {
    "beauty": ["美妆", "护肤", "护肤品", "化妆品", "彩妆"],
    "apparel": ["服饰", "运动类", "运动用品", "健身", "训练", "瑜伽", "跑步", "徒步", "运动鞋", "运动服"],
    "digital": ["数码", "电子", "手机", "电脑", "平板", "耳机", "拍照", "续航"],
    "food": ["食品", "饮料", "零食", "咖啡", "茶饮", "减脂", "控糖", "低糖", "无糖", "提神"],
}


class PlannerBudgetUpdate(BaseModel):
    type: Literal["keep", "set", "relax", "unknown"] = "keep"
    value: float | None = None


class PlannerCategoryPatch(BaseModel):
    mode: Literal["keep", "replace", "add", "exclude", "unknown"] = "keep"
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    reason_type: Literal[
        "none",
        "explicit_exclusion",
        "category_switch",
        "gift_broadening",
        "unclear",
    ] = "none"


class PlannerComparisonPlan(BaseModel):
    enabled: bool = False
    target_policy: Literal[
        "none",
        "latest_all_products",
        "latest_first_n",
        "mentioned_product_ids",
        "mentioned_product_names",
        "unknown",
    ] = "none"
    target_product_ids: list[str] = Field(default_factory=list)
    target_indexes: list[int] = Field(default_factory=list)
    focus_dimensions: list[str] = Field(default_factory=list)
    output_format: Literal["markdown_table"] = "markdown_table"
    needs_clarification: bool = False
    clarification_question: str | None = None


class RetrievalPlan(BaseModel):
    turn_type: Literal[
        "new_search",
        "refine_search",
        "product_followup",
        "compare",
        "clarify",
        "reset",
        "chitchat",
    ] = "new_search"
    rewrite_query: str = ""
    budget_update: PlannerBudgetUpdate = Field(default_factory=PlannerBudgetUpdate)
    category_patch: PlannerCategoryPatch = Field(default_factory=PlannerCategoryPatch)
    facets_patch: dict[str, list[str]] = Field(default_factory=dict)
    exclude_terms_patch: list[str] = Field(default_factory=list)
    referenced_product_policy: Literal[
        "none",
        "previous_top_product",
        "mentioned_product_ids",
        "unknown",
    ] = "none"
    comparison_plan: PlannerComparisonPlan = Field(default_factory=PlannerComparisonPlan)
    needs_clarification: bool = False
    clarification_question: str | None = None
    confidence: float = 0.0


async def build_planned_retrieval_message(
    settings: Settings,
    request: ChatRequest,
) -> RetrievalMessageBuildResult:
    rule_build = build_retrieval_message(request)
    planner_trace: dict[str, object] = {
        "enabled": True,
        "called": False,
        "applied": False,
        "fallback_reason": None,
        "latency_ms": None,
        "raw_plan": {},
        "validated_plan": {},
        "validation_errors": [],
    }

    if settings.mock_llm or not settings.llm_configured:
        planner_trace["fallback_reason"] = "planner_disabled_by_mock_or_missing_llm_config"
        return _with_planner_trace(rule_build, planner_trace)

    started = time.perf_counter()
    try:
        planner_trace["called"] = True
        raw_payload = await asyncio.wait_for(
            _collect_plan_payload(settings=settings, request=request, rule_build=rule_build),
            timeout=settings.planner_timeout_seconds,
        )
        planner_trace["raw_plan"] = raw_payload
        plan = RetrievalPlan.model_validate(raw_payload)
    except TimeoutError:
        planner_trace["fallback_reason"] = "planner_timeout"
        return _finish_planner_trace(rule_build, planner_trace, started)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        planner_trace["fallback_reason"] = "planner_invalid_json_or_schema"
        planner_trace["validation_errors"] = [str(exc)]
        return _finish_planner_trace(rule_build, planner_trace, started)
    except Exception as exc:
        logger.warning("Planner response failed; falling back to rule-only retrieval: %s", exc)
        planner_trace["fallback_reason"] = f"planner_api_error:{exc.__class__.__name__}"
        planner_trace["validation_errors"] = [str(exc)]
        return _finish_planner_trace(rule_build, planner_trace, started)

    validated_plan, additions, validation_errors = _validate_plan(plan, request, rule_build)
    planner_trace["validated_plan"] = validated_plan
    planner_trace["validation_errors"] = validation_errors
    if not additions:
        planner_trace["fallback_reason"] = "planner_no_valid_delta"
        return _finish_planner_trace(rule_build, planner_trace, started)

    planner_trace["applied"] = True
    merged_message = _append_planner_additions(rule_build.message, additions, request.message)
    return _finish_planner_trace(
        RetrievalMessageBuildResult(
            message=merged_message,
            applied=True,
            trace={
                **rule_build.trace,
                "planner_trace": planner_trace,
            },
        ),
        planner_trace,
        started,
    )


async def _collect_plan_payload(
    settings: Settings,
    request: ChatRequest,
    rule_build: RetrievalMessageBuildResult,
) -> dict:
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.planner_timeout_seconds,
    )
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _planner_user_prompt(request=request, rule_build=rule_build),
                },
            ],
            temperature=0.0,
            max_tokens=650,
        )
        content = response.choices[0].message.content or ""
        return _loads_json_object(content)
    finally:
        await client.close()


PLANNER_SYSTEM_PROMPT = """你是电商 RAG 系统的检索计划器，只输出 JSON，不输出解释。
你的任务是把用户当前轮和历史对话翻译成可校验的检索计划。
禁止生成商品事实、价格、库存、优惠、功效承诺或最终导购回答。
如果不确定，就写 keep / unknown / none，不要猜。
预算、排除条件、商品事实等硬约束必须保守处理。
"""


def _planner_user_prompt(request: ChatRequest, rule_build: RetrievalMessageBuildResult) -> str:
    history_lines = []
    for item in request.history[-8:]:
        product_ids = f" product_ids={item.product_ids}" if item.product_ids else ""
        history_lines.append(f"- {item.role}: {item.content}{product_ids}")
    history = "\n".join(history_lines) if history_lines else "无"
    rule_trace = rule_build.trace.get("constraint_trace", {})
    allowed_facets = {
        facet_name: list(values.keys())
        for facet_name, values in FACET_LEXICON.items()
    }
    schema = {
        "turn_type": "new_search | refine_search | product_followup | compare | clarify | reset | chitchat",
        "rewrite_query": "string, 不要加入用户没说过的商品事实",
        "budget_update": {"type": "keep | set | relax | unknown", "value": "number or null"},
        "category_patch": {
            "mode": "keep | replace | add | exclude | unknown",
            "include": list(CATEGORY_TO_RAW.keys()),
            "exclude": list(CATEGORY_TO_RAW.keys()),
            "reason_type": "none | explicit_exclusion | category_switch | gift_broadening | unclear",
        },
        "facets_patch": allowed_facets,
        "exclude_terms_patch": EXCLUDE_TERMS,
        "referenced_product_policy": "none | previous_top_product | mentioned_product_ids | unknown",
        "comparison_plan": {
            "enabled": "boolean",
            "target_policy": "none | latest_all_products | latest_first_n | mentioned_product_ids | mentioned_product_names | unknown",
            "target_product_ids": "array of product ids already present in history.product_ids only",
            "target_indexes": "0-based indexes when user says first/second/前两个",
            "focus_dimensions": "array of short user-mentioned comparison dimensions",
            "output_format": "markdown_table",
            "needs_clarification": "boolean",
            "clarification_question": "string or null",
        },
        "needs_clarification": "boolean",
        "clarification_question": "string or null",
        "confidence": "0.0-1.0",
    }
    return (
        "请只返回一个 JSON object，字段必须与下面 schema 对齐。\n\n"
        f"schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "校验规则：\n"
        "- budget_update.type=set 时，value 必须是用户当前轮明确给出的预算数字；例如“预算可能只有150”应输出 150。\n"
        "- 用户说“先不看预算/不限预算/放宽预算”但没给数字时，budget_update.type=relax。\n"
        "- 用户说“非/不是/不要/不看/不太想要/除了/换个别的”某类目时，必须用 category_patch 表达排除或替换；例如“非化妆品运动类”应 exclude beauty，并 include apparel。\n"
        "- category_patch.include/exclude 只能使用 beauty/apparel/digital/food；不要发明类目。\n"
        "- facets_patch 只能使用 schema 中列出的枚举值；不要因为“夏天”直接推断“户外”。\n"
        "- exclude_terms_patch 只能使用用户明确说要避开的词。\n"
        "- referenced_product_policy 只能用于“它/这款/第一款/刚才那款”等指代；不能捏造商品 ID。\n"
        "- 如果用户要求对比/怎么选/哪个更适合，turn_type=compare，并填写 comparison_plan。\n"
        "- comparison_plan.target_product_ids 只能来自历史 product_ids；如果用户只是点名品牌/商品名但历史没有对应 ID，target_policy=mentioned_product_names，不要编 ID。\n"
        "- 用户说“这几个/它们/都对比”时，target_policy=latest_all_products；说“前两个”时，target_policy=latest_first_n 且 target_indexes=[0,1]。\n"
        "- 不要输出推理过程。\n\n"
        f"历史对话：\n{history}\n\n"
        f"当前用户消息：\n{request.message}\n\n"
        f"规则基线检索消息：\n{rule_build.message}\n\n"
        f"规则基线 trace：\n{json.dumps(rule_trace, ensure_ascii=False)}"
    )


def _loads_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if "{" not in text or "}" not in text:
        raise ValueError("planner response did not contain a JSON object")
    start = text.find("{")
    end = text.rfind("}") + 1
    payload = json.loads(text[start:end])
    if not isinstance(payload, dict):
        raise ValueError("planner response JSON is not an object")
    return payload


def _validate_plan(
    plan: RetrievalPlan,
    request: ChatRequest,
    rule_build: RetrievalMessageBuildResult,
) -> tuple[dict[str, object], list[str], list[str]]:
    validation_errors: list[str] = []
    additions: list[str] = []
    validated: dict[str, object] = {
        "turn_type": plan.turn_type,
        "rewrite_query": _clean_text(plan.rewrite_query, limit=180),
        "budget_update": {"type": "keep", "value": None},
        "category_patch": {"mode": "keep", "include": [], "exclude": [], "reason_type": "none"},
        "facets_patch": {},
        "exclude_terms_patch": [],
        "referenced_product_ids": [],
        "referenced_product_policy": plan.referenced_product_policy,
        "comparison_plan": {},
        "needs_clarification": plan.needs_clarification,
        "clarification_question": _clean_text(plan.clarification_question or "", limit=80) or None,
        "confidence": max(0.0, min(float(plan.confidence), 1.0)),
    }

    budget_line = _validate_budget_update(plan, request, rule_build, validation_errors)
    if budget_line:
        additions.append(budget_line)
        budget = plan.budget_update.value if plan.budget_update.type == "set" else None
        validated["budget_update"] = {"type": plan.budget_update.type, "value": budget}

    category_lines, category_patch = _validate_category_patch(plan, request, validation_errors)
    additions.extend(category_lines)
    validated["category_patch"] = category_patch

    facet_lines, facets = _validate_facets(plan, request, validation_errors)
    additions.extend(facet_lines)
    validated["facets_patch"] = facets

    exclude_line, excludes = _validate_excludes(plan, request, validation_errors)
    if exclude_line:
        additions.append(exclude_line)
    validated["exclude_terms_patch"] = excludes

    referenced_ids = _validate_product_reference(plan, request, validation_errors)
    if referenced_ids:
        additions.append(f"- 指代商品ID：{'、'.join(referenced_ids)}")
    validated["referenced_product_ids"] = referenced_ids

    comparison_plan, comparison_lines = _validate_comparison_plan(plan, request, validation_errors)
    if comparison_lines:
        additions.extend(comparison_lines)
    validated["comparison_plan"] = comparison_plan

    return validated, additions, validation_errors


def _validate_budget_update(
    plan: RetrievalPlan,
    request: ChatRequest,
    rule_build: RetrievalMessageBuildResult,
    validation_errors: list[str],
) -> str | None:
    update = plan.budget_update
    if update.type == "set":
        if update.value is None or update.value <= 0:
            validation_errors.append("budget_update.set_without_positive_value")
            return None
        if not _budget_value_mentioned(update.value, request.message):
            validation_errors.append(f"budget_update.value_not_in_current_turn:{update.value:g}")
            return None
        return f"- 预算：{update.value:g}元以内"
    if update.type == "relax":
        rule_relaxed = "budget_max" in (
            rule_build.trace.get("constraint_trace", {}).get("relaxed", [])
        )
        if rule_relaxed or _looks_like_budget_relax(request.message):
            return "- 预算：不限制"
        validation_errors.append("budget_update.relax_without_user_signal")
    return None


def _validate_category_patch(
    plan: RetrievalPlan,
    request: ChatRequest,
    validation_errors: list[str],
) -> tuple[list[str], dict[str, object]]:
    patch = plan.category_patch
    validated: dict[str, object] = {
        "mode": patch.mode,
        "include": [],
        "exclude": [],
        "reason_type": patch.reason_type,
    }
    if patch.mode in {"keep", "unknown"}:
        return [], validated

    current_text = request.message
    accepted_include = _accepted_categories(
        patch.include,
        validation_errors=validation_errors,
        error_prefix="category_patch.include",
    )
    accepted_exclude = _accepted_categories(
        patch.exclude,
        validation_errors=validation_errors,
        error_prefix="category_patch.exclude",
    )

    if patch.mode in {"replace", "add"}:
        accepted_include = [
            category for category in accepted_include
            if _category_include_signaled(category, current_text)
        ]
        rejected_include = [
            category for category in patch.include
            if category in CATEGORY_TO_RAW and category not in accepted_include
        ]
        validation_errors.extend(
            f"category_include_without_current_signal:{category}"
            for category in rejected_include
        )
    else:
        accepted_include = []

    if patch.mode in {"replace", "exclude"}:
        accepted_exclude = [
            category for category in accepted_exclude
            if _category_exclusion_signaled(category, current_text)
        ]
        rejected_exclude = [
            category for category in patch.exclude
            if category in CATEGORY_TO_RAW and category not in accepted_exclude
        ]
        validation_errors.extend(
            f"category_exclude_without_current_signal:{category}"
            for category in rejected_exclude
        )
    else:
        accepted_exclude = []

    lines: list[str] = []
    if accepted_include:
        lines.append(f"- 类目：{'、'.join(CATEGORY_TO_RAW[category] for category in accepted_include)}")
    if accepted_exclude:
        lines.append(f"- 排除类目：不要{'、'.join(CATEGORY_TO_RAW[category] for category in accepted_exclude)}")

    if not lines:
        return [], validated

    validated["include"] = accepted_include
    validated["exclude"] = accepted_exclude
    return lines, validated


def _accepted_categories(
    categories: list[str],
    *,
    validation_errors: list[str],
    error_prefix: str,
) -> list[str]:
    accepted: list[str] = []
    for raw_category in categories:
        category = str(raw_category).strip()
        if category not in CATEGORY_TO_RAW:
            validation_errors.append(f"{error_prefix}.unknown:{category}")
            continue
        accepted.append(category)
    return list(dict.fromkeys(accepted))


def _category_include_signaled(category: str, current_text: str) -> bool:
    aliases = CATEGORY_SIGNAL_ALIASES.get(category, [])
    lowered = current_text.lower()
    return any(alias.lower() in lowered for alias in aliases)


def _category_exclusion_signaled(category: str, current_text: str) -> bool:
    if category in category_exclusions(current_text):
        return True
    aliases = CATEGORY_SIGNAL_ALIASES.get(category, [])
    negative_terms = [
        "非",
        "不是",
        "不要",
        "不看",
        "别看",
        "排除",
        "避开",
        "不想要",
        "不太想要",
        "不考虑",
        "不太行",
        "除外",
        "之外",
        "以外",
    ]
    for alias in aliases:
        alias_pattern = re.escape(alias)
        negative_pattern = "|".join(re.escape(term) for term in negative_terms)
        if re.search(rf"(?:{negative_pattern}).{{0,12}}{alias_pattern}", current_text):
            return True
        if re.search(rf"{alias_pattern}.{{0,12}}(?:{negative_pattern})", current_text):
            return True
    return False


def _validate_facets(
    plan: RetrievalPlan,
    request: ChatRequest,
    validation_errors: list[str],
) -> tuple[list[str], dict[str, list[str]]]:
    combined_user_text = _combined_user_text(request)
    lines: list[str] = []
    validated: dict[str, list[str]] = {}
    label_by_facet = {
        "skin_type": "肤质",
        "effect": "功效",
        "use_case": "场景",
        "sub_category": "子类",
    }
    for facet_name, values in plan.facets_patch.items():
        allowed = FACET_LEXICON.get(facet_name)
        if allowed is None:
            validation_errors.append(f"unknown_facet:{facet_name}")
            continue
        accepted: list[str] = []
        for raw_value in values:
            value = str(raw_value).strip()
            if value not in allowed:
                validation_errors.append(f"unknown_facet_value:{facet_name}={value}")
                continue
            aliases = allowed[value]
            if not any(alias.lower() in combined_user_text.lower() for alias in aliases):
                validation_errors.append(f"facet_without_user_signal:{facet_name}={value}")
                continue
            accepted.append(value)
        if accepted:
            accepted = list(dict.fromkeys(accepted))
            validated[facet_name] = accepted
            lines.append(f"- {label_by_facet.get(facet_name, facet_name)}：{'、'.join(accepted)}")
    return lines, validated


def _validate_excludes(
    plan: RetrievalPlan,
    request: ChatRequest,
    validation_errors: list[str],
) -> tuple[str | None, list[str]]:
    combined_user_text = _combined_user_text(request)
    accepted: list[str] = []
    for raw_term in plan.exclude_terms_patch:
        term = str(raw_term).strip()
        if term not in EXCLUDE_TERMS:
            validation_errors.append(f"unknown_exclude_term:{term}")
            continue
        if term not in combined_user_text:
            validation_errors.append(f"exclude_without_user_signal:{term}")
            continue
        accepted.append(term)
    accepted = list(dict.fromkeys(accepted))
    if not accepted:
        return None, []
    return f"- 排除：不要{'、'.join(accepted)}", accepted


def _validate_product_reference(
    plan: RetrievalPlan,
    request: ChatRequest,
    validation_errors: list[str],
) -> list[str]:
    if plan.referenced_product_policy not in {"previous_top_product", "mentioned_product_ids"}:
        return []
    product_ids = _latest_history_product_ids(request.history)
    if not product_ids:
        validation_errors.append("referenced_product_without_history_products")
        return []
    index = _referenced_product_index(request.message)
    if index is not None:
        if index < len(product_ids):
            return [product_ids[index]]
        validation_errors.append(f"referenced_product_index_out_of_range:{index + 1}")
        return []
    if any(term in request.message for term in ["它", "这个", "这款", "刚才", "上一款"]):
        return [product_ids[0]]
    return []


def _validate_comparison_plan(
    plan: RetrievalPlan,
    request: ChatRequest,
    validation_errors: list[str],
) -> tuple[dict[str, object], list[str]]:
    if plan.turn_type != "compare" and not plan.comparison_plan.enabled:
        return {}, []

    latest_product_ids = _latest_history_product_ids(request.history)
    target_ids = _comparison_target_ids_from_history(plan.comparison_plan, request.message, latest_product_ids)
    if not target_ids and plan.comparison_plan.target_product_ids:
        validation_errors.append("comparison_target_ids_not_in_history")

    focus_dimensions = _comparison_focus_dimensions(plan.comparison_plan.focus_dimensions, request.message)
    comparison_plan: dict[str, object] = {
        "enabled": True,
        "target_policy": plan.comparison_plan.target_policy,
        "target_product_ids": target_ids,
        "target_indexes": plan.comparison_plan.target_indexes[:4],
        "focus_dimensions": focus_dimensions,
        "output_format": "markdown_table",
        "needs_clarification": plan.comparison_plan.needs_clarification,
        "clarification_question": _clean_text(plan.comparison_plan.clarification_question or "", limit=80) or None,
    }
    lines = ["- 意图：对比/选择", "- 输出形式：Markdown对比表"]
    if target_ids:
        lines.append(f"- 指代商品ID：{'、'.join(target_ids)}")
    if focus_dimensions:
        lines.append(f"- 对比关注点：{'、'.join(focus_dimensions)}")
    return comparison_plan, lines


def _comparison_target_ids_from_history(
    comparison_plan: PlannerComparisonPlan,
    message: str,
    latest_product_ids: list[str],
) -> list[str]:
    if not latest_product_ids:
        return []
    target_ids = [
        product_id
        for product_id in comparison_plan.target_product_ids
        if product_id in latest_product_ids
    ]
    if target_ids:
        return list(dict.fromkeys(target_ids))

    indexes = _comparison_indexes(message)
    if comparison_plan.target_indexes:
        indexes.extend(index for index in comparison_plan.target_indexes if isinstance(index, int))
    indexes = list(dict.fromkeys(indexes))
    if indexes:
        return [latest_product_ids[index] for index in indexes if 0 <= index < len(latest_product_ids)]

    if comparison_plan.target_policy == "latest_first_n" or _references_first_two_products(message):
        return latest_product_ids[:2]
    if comparison_plan.target_policy == "latest_all_products" or _references_all_previous_products(message):
        return latest_product_ids
    return []


def _comparison_indexes(message: str) -> list[int]:
    normalized = message.strip()
    if _references_first_two_products(normalized):
        return [0, 1]
    markers = [
        (r"(第一|第1(?:个|款|件)?|1(?:号|个|款|件))", 0),
        (r"(第二|第2(?:个|款|件)?|2(?:号|个|款|件))", 1),
        (r"(第三|第3(?:个|款|件)?|3(?:号|个|款|件))", 2),
    ]
    indexes = [index for pattern, index in markers if re.search(pattern, normalized)]
    if _has_numbered_comparison_context(normalized):
        bare_markers = [
            (r"(?<!\d)[1一](?!\d)", 0),
            (r"(?<!\d)[2二](?!\d)", 1),
            (r"(?<!\d)[3三](?!\d)", 2),
        ]
        indexes.extend(index for pattern, index in bare_markers if re.search(pattern, normalized))
    if indexes and any(term in normalized for term in ["它", "这个", "这款", "刚才那个", "刚才那款", "上一款", "上一个"]):
        indexes.insert(0, 0)
    return list(dict.fromkeys(indexes))


def _comparison_focus_dimensions(raw_dimensions: list[str], message: str) -> list[str]:
    allowed_by_signal = [
        ("价格", ["价格", "预算", "便宜", "贵", "性价比"]),
        ("适合肤质", ["肤质", "油皮", "干皮", "敏感", "混油", "混干"]),
        ("通勤场景", ["通勤", "上班", "日常"]),
        ("户外/防水防汗", ["户外", "防水", "防汗", "海边", "运动"]),
        ("补涂方便度", ["补涂", "便携", "随身"]),
        ("注意事项", ["注意", "风险", "过敏", "敏感", "避开"]),
    ]
    dimensions: list[str] = []
    for label, signals in allowed_by_signal:
        if any(signal in message for signal in signals):
            dimensions.append(label)
    for raw in raw_dimensions:
        cleaned = _clean_text(str(raw), limit=16)
        if cleaned and any(signal in message for signal in [cleaned, cleaned.lower()]):
            dimensions.append(cleaned)
    return list(dict.fromkeys(dimensions))[:6]


def _references_first_two_products(message: str) -> bool:
    return bool(re.search(r"(前两|前二|前2|前两个|前二个|前两款|前2款)", message))


def _references_all_previous_products(message: str) -> bool:
    normalized_message = re.sub(r"比较(合适|适合|舒服|稳妥|好|划算|便宜|贵|大|小)", "", message)
    if not any(term in normalized_message for term in ["对比", "比较", "怎么选", "哪个更", "哪款更", "区别"]):
        return False
    return any(term in normalized_message for term in ["这几个", "这些", "它们", "刚才这些", "刚才几个", "全部", "都"])


def _append_planner_additions(rule_message: str, additions: list[str], current_message: str) -> str:
    return "\n".join(
        [
            rule_message,
            "LLM Planner补充：",
            *additions,
            "本轮原文：",
            current_message,
        ]
    )


def _with_planner_trace(
    result: RetrievalMessageBuildResult,
    planner_trace: dict[str, object],
) -> RetrievalMessageBuildResult:
    return RetrievalMessageBuildResult(
        message=result.message,
        applied=result.applied,
        trace={
            **result.trace,
            "planner_trace": planner_trace,
        },
    )


def _finish_planner_trace(
    result: RetrievalMessageBuildResult,
    planner_trace: dict[str, object],
    started: float,
) -> RetrievalMessageBuildResult:
    planner_trace["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return _with_planner_trace(result, planner_trace)


def _combined_user_text(request: ChatRequest) -> str:
    history_text = "\n".join(
        item.content
        for item in request.history[-8:]
        if item.role == "user"
    )
    return f"{history_text}\n{request.message}"


def _latest_history_product_ids(history: list[ChatMessage]) -> list[str]:
    for item in reversed(history):
        if item.role == "assistant" and item.product_ids:
            return item.product_ids
    return []


def _referenced_product_index(message: str) -> int | None:
    markers = [
        ("第一", 0),
        ("第1", 0),
        ("1款", 0),
        ("第二", 1),
        ("第2", 1),
        ("2款", 1),
        ("第三", 2),
        ("第3", 2),
        ("3款", 2),
    ]
    for marker, index in markers:
        if marker in message:
            return index
    return None


def _has_numbered_comparison_context(message: str) -> bool:
    return any(term in message for term in ["比较", "对比", "1和", "1 和", "一和", "一 和", "和2", "和 2", "和二", "和 二"])


def _budget_value_mentioned(value: float, message: str) -> bool:
    normalized_value = f"{value:g}"
    if normalized_value in message:
        return True
    if float(value).is_integer() and str(int(value)) in message:
        return True
    return False


def _looks_like_budget_relax(message: str) -> bool:
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


def _clean_text(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]
