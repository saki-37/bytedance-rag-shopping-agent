#!/usr/bin/env python3
"""Smoke-test the lightweight LLM Planner contract without network access."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.config import Settings  # noqa: E402
from app.conversation_state import build_retrieval_message  # noqa: E402
from app.models import ChatMessage, ChatRequest  # noqa: E402
from app.planner import RetrievalPlan, _append_planner_additions, _validate_plan, build_planned_retrieval_message  # noqa: E402
from app.retrieval import parse_query_intent  # noqa: E402


def main() -> None:
    check_budget_parser()
    check_category_switch_parser()
    check_planner_category_patch()
    check_planner_validator()
    asyncio.run(check_planner_fallback())
    print("Planner contract checks passed")


def check_budget_parser() -> None:
    cases = {
        "我的预算可能只有150": 150.0,
        "预算只有150": 150.0,
        "我的预算可能只有150元": 150.0,
        "大概150以内": 150.0,
        "预算150": 150.0,
    }
    for query, expected in cases.items():
        actual = parse_query_intent(query).universal_constraints.budget_max
        assert actual == expected, (query, actual, expected)


def check_category_switch_parser() -> None:
    direct_intent = parse_query_intent("有没有什么运动类的非化妆品推荐？")
    assert direct_intent.category_candidates == ["apparel"], direct_intent.category_candidates

    request = ChatRequest(
        message="有没有什么运动类的非化妆品推荐？",
        history=[
            ChatMessage(role="user", content="我想给我妈买生日礼物，你有什么推荐吗？"),
            ChatMessage(role="assistant", content="你更在意预算、送礼/自用场景、品类方向，还是需要避开的条件？"),
            ChatMessage(
                role="user",
                content="我妈皮肤比较敏感，如果是化妆品类要求会很高。她最近在减脂，也对运动比较感兴趣，预算500元以内。",
            ),
            ChatMessage(role="assistant", content="先给了几款美妆候选。", product_ids=["p_beauty_018", "p_beauty_010", "p_beauty_014"]),
            ChatMessage(role="user", content="有没有什么运动类的推荐？"),
            ChatMessage(role="assistant", content="先给了运动场景相关候选。", product_ids=["p_beauty_020", "p_beauty_010"]),
        ],
    )
    rule_build = build_retrieval_message(request)
    assert "- 类目：服饰运动" in rule_build.message, rule_build.message
    assert "- 类目：美妆护肤" not in rule_build.message, rule_build.message
    assert "- 肤质：" not in rule_build.message, rule_build.message
    merged_intent = parse_query_intent(rule_build.message)
    assert merged_intent.category_candidates == ["apparel"], merged_intent.category_candidates


def check_planner_category_patch() -> None:
    request = ChatRequest(
        message="化妆品我不太想要，想看看运动类礼物",
        history=[
            ChatMessage(role="user", content="我想给我妈买生日礼物，你有什么推荐吗？"),
            ChatMessage(role="assistant", content="先给了几款美妆候选。", product_ids=["p_beauty_018", "p_beauty_010", "p_beauty_014"]),
        ],
    )
    rule_build = build_retrieval_message(request)
    plan = RetrievalPlan.model_validate(
        {
            "turn_type": "refine_search",
            "rewrite_query": "妈妈生日礼物 运动类 非化妆品",
            "budget_update": {"type": "keep", "value": None},
            "category_patch": {
                "mode": "replace",
                "include": ["apparel"],
                "exclude": ["beauty"],
                "reason_type": "explicit_exclusion",
            },
            "facets_patch": {"use_case": ["运动"]},
            "exclude_terms_patch": [],
            "referenced_product_policy": "none",
            "needs_clarification": False,
            "clarification_question": None,
            "confidence": 0.9,
        }
    )
    validated, additions, errors = _validate_plan(plan, request, rule_build)
    assert not errors, errors
    assert validated["category_patch"] == {
        "mode": "replace",
        "include": ["apparel"],
        "exclude": ["beauty"],
        "reason_type": "explicit_exclusion",
    }
    assert "- 类目：服饰运动" in additions
    assert "- 排除类目：不要美妆护肤" in additions
    merged = _append_planner_additions(rule_build.message, additions, request.message)
    assert parse_query_intent(merged).category_candidates == ["apparel"], merged


def check_planner_validator() -> None:
    request = ChatRequest(
        message="我的预算可能只有150",
        history=[
            ChatMessage(role="user", content="夏天快到了，想看看防晒!"),
            ChatMessage(role="assistant", content="已返回商品卡片。", product_ids=["p_beauty_010", "p_beauty_023", "p_beauty_006"]),
            ChatMessage(role="user", content="我是油皮，主要是户外需求"),
        ],
    )
    rule_build = build_retrieval_message(request)
    plan = RetrievalPlan.model_validate(
        {
            "turn_type": "refine_search",
            "rewrite_query": "油皮 户外 防晒 150元以内",
            "budget_update": {"type": "set", "value": 150},
            "facets_patch": {
                "skin_type": ["油皮"],
                "effect": ["防晒"],
                "use_case": ["户外"],
            },
            "exclude_terms_patch": [],
            "referenced_product_policy": "none",
            "needs_clarification": False,
            "clarification_question": None,
            "confidence": 0.9,
        }
    )
    validated, additions, errors = _validate_plan(plan, request, rule_build)
    assert not errors, errors
    assert validated["budget_update"] == {"type": "set", "value": 150.0}
    assert "- 预算：150元以内" in additions
    assert "- 肤质：油皮" in additions
    merged = _append_planner_additions(rule_build.message, additions, request.message)
    assert "LLM Planner补充" in merged
    assert parse_query_intent(merged).universal_constraints.budget_max == 150.0


async def check_planner_fallback() -> None:
    settings = Settings(mock_llm=True, ark_api_key=None, ark_model=None)
    request = ChatRequest(message="我的预算可能只有150")
    result = await build_planned_retrieval_message(settings, request)
    trace = result.trace["planner_trace"]
    assert trace["called"] is False
    assert trace["applied"] is False
    assert trace["fallback_reason"] == "planner_disabled_by_mock_or_missing_ark_config"


if __name__ == "__main__":
    main()
