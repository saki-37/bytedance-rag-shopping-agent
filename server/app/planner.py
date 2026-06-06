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
from app.retrieval import EXCLUDE_TERMS, FACET_LEXICON, parse_query_intent


logger = logging.getLogger(__name__)


class PlannerBudgetUpdate(BaseModel):
    type: Literal["keep", "set", "relax", "unknown"] = "keep"
    value: float | None = None


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
    facets_patch: dict[str, list[str]] = Field(default_factory=dict)
    exclude_terms_patch: list[str] = Field(default_factory=list)
    referenced_product_policy: Literal[
        "none",
        "previous_top_product",
        "mentioned_product_ids",
        "unknown",
    ] = "none"
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

    if settings.mock_llm or not settings.ark_api_key or not settings.ark_model:
        planner_trace["fallback_reason"] = "planner_disabled_by_mock_or_missing_ark_config"
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
        api_key=settings.ark_api_key,
        base_url=settings.ark_base_url,
        timeout=settings.planner_timeout_seconds,
    )
    try:
        response = await client.chat.completions.create(
            model=settings.ark_model,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _planner_user_prompt(request=request, rule_build=rule_build),
                },
            ],
            temperature=0.0,
            max_tokens=450,
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
        "facets_patch": allowed_facets,
        "exclude_terms_patch": EXCLUDE_TERMS,
        "referenced_product_policy": "none | previous_top_product | mentioned_product_ids | unknown",
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
        "- facets_patch 只能使用 schema 中列出的枚举值；不要因为“夏天”直接推断“户外”。\n"
        "- exclude_terms_patch 只能使用用户明确说要避开的词。\n"
        "- referenced_product_policy 只能用于“它/这款/第一款/刚才那款”等指代；不能捏造商品 ID。\n"
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
        "facets_patch": {},
        "exclude_terms_patch": [],
        "referenced_product_ids": [],
        "referenced_product_policy": plan.referenced_product_policy,
        "needs_clarification": plan.needs_clarification,
        "clarification_question": _clean_text(plan.clarification_question or "", limit=80) or None,
        "confidence": max(0.0, min(float(plan.confidence), 1.0)),
    }

    budget_line = _validate_budget_update(plan, request, rule_build, validation_errors)
    if budget_line:
        additions.append(budget_line)
        budget = plan.budget_update.value if plan.budget_update.type == "set" else None
        validated["budget_update"] = {"type": plan.budget_update.type, "value": budget}

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
