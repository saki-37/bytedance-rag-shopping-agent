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
from app.data_loader import load_enriched_products, load_raw_products  # noqa: E402
from app.models import ChatMessage, ChatRequest  # noqa: E402
from app.planner import RetrievalPlan, _append_planner_additions, _validate_plan, build_planned_retrieval_message  # noqa: E402
from app.retrieval import parse_query_intent, retrieve  # noqa: E402


def main() -> None:
    check_budget_parser()
    check_comparison_phrase_parser()
    check_category_switch_parser()
    check_numeric_comparison_pair_parser()
    check_history_brand_followup_parser()
    check_recent_product_type_followup_parser()
    check_planner_category_patch()
    check_planner_scene_bundle_plan()
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


def check_comparison_phrase_parser() -> None:
    assert not parse_query_intent("穿多大的比较合适？").comparison_mode
    assert not parse_query_intent("这个尺码会不会比较大？").comparison_mode
    assert parse_query_intent("可以帮我比较一下1和2吗？").comparison_mode
    assert parse_query_intent("这两款有什么区别？").comparison_mode


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


def check_numeric_comparison_pair_parser() -> None:
    settings = Settings(mock_llm=True)
    products = load_enriched_products(settings.enriched_data_dir, load_raw_products(settings.raw_data_dir))
    history = [
        ChatMessage(role="user", content="有没有什么运动类的非化妆品推荐？"),
        ChatMessage(
            role="assistant",
            content=(
                "给你推荐3款符合你需求的500元以内运动类非化妆品好物：\n"
                "1. 优衣库 男装 DRY 速干运动短裤。\n"
                "2. adidas Essentials 三条纹 男子针织运动长裤。\n"
                "3. 李宁 运动生活系列 男子连帽套头卫衣。"
            ),
            product_ids=["p_clothes_023", "p_clothes_004", "p_clothes_005"],
        )
    ]
    for message in ["可以帮我比较一下1和2吗？", "可以帮我比较一下1 和 2吗？", "可以帮我比较一下一和二吗？"]:
        request = ChatRequest(message=message, history=history)
        rule_build = build_retrieval_message(request)
        intent = parse_query_intent(rule_build.message)
        assert intent.referenced_product_ids == ["p_clothes_023", "p_clothes_004"], (message, rule_build.message)
        assert "p_clothes_005" not in intent.referenced_product_ids, (message, intent.referenced_product_ids)
        assert intent.comparison_mode
        result = retrieve(rule_build.message, products)
        assert [card.product_id for card in result.cards] == ["p_clothes_023", "p_clothes_004"], (
            message,
            [card.product_id for card in result.cards],
        )


def check_history_brand_followup_parser() -> None:
    request = ChatRequest(
        message="好的，我觉得阿迪达斯的不错。然后我妈是168厘米，体重是130斤，穿多大的比较合适？",
        history=[
            ChatMessage(
                role="assistant",
                content=(
                    "给你推荐3款500元以内的运动类非化妆品好物：\n"
                    "1. 优衣库 男装 DRY 速干运动短裤。\n"
                    "2. adidas Essentials 三条纹 男子针织运动长裤。\n"
                    "3. 李宁 运动生活系列 男子连帽套头卫衣。"
                ),
                product_ids=["p_clothes_023", "p_clothes_004", "p_clothes_005"],
            ),
            ChatMessage(role="user", content="可以帮我比较一下1和2吗？"),
            ChatMessage(
                role="assistant",
                content=(
                    "| 商品名称 | 价格 | 选择建议 |\n"
                    "| --- | --- | --- |\n"
                    "| 优衣库 男装 DRY 速干运动短裤 | ¥149起 | 适合夏季短时间运动 |\n"
                    "| adidas Essentials 三条纹 男子针织运动长裤 | ¥299起 | 适合通勤和春秋运动 |"
                ),
                product_ids=["p_clothes_023", "p_clothes_004"],
            ),
        ],
    )
    rule_build = build_retrieval_message(request)
    assert "p_clothes_004" in rule_build.message, rule_build.message
    assert "p_clothes_022" not in rule_build.message, rule_build.message
    intent = parse_query_intent(rule_build.message)
    assert intent.referenced_product_ids == ["p_clothes_004"], intent.referenced_product_ids
    assert not intent.comparison_mode


def check_recent_product_type_followup_parser() -> None:
    history = [
        ChatMessage(
            role="assistant",
            content=(
                "给你推荐3款500元以内的运动类非化妆品好物：\n"
                "1. 优衣库 男装 DRY 速干运动短裤。\n"
                "2. adidas Essentials 三条纹 男子针织运动长裤。\n"
                "3. 李宁 运动生活系列 男子连帽套头卫衣。"
            ),
            product_ids=["p_clothes_023", "p_clothes_004", "p_clothes_005"],
        ),
        ChatMessage(role="user", content="可以帮我比较一下1和2吗？"),
        ChatMessage(
            role="assistant",
            content=(
                "| 商品名称 | 价格 | 选择建议 |\n"
                "| --- | --- | --- |\n"
                "| 优衣库 男装 DRY 速干运动短裤 | ¥149起 | 适合夏季短时间运动 |\n"
                "| adidas Essentials 三条纹 男子针织运动长裤 | ¥299起 | 适合通勤和春秋运动 |"
            ),
            product_ids=["p_clothes_023", "p_clothes_004"],
        ),
    ]

    long_pants_request = ChatRequest(
        message="好的，我觉得长裤不错。然后我妈是168厘米，体重是130斤，穿多大的比较合适？",
        history=history,
    )
    long_build = build_retrieval_message(long_pants_request)
    long_intent = parse_query_intent(long_build.message)
    assert long_intent.referenced_product_ids == ["p_clothes_004"], long_build.message
    assert not long_intent.comparison_mode

    shorts_request = ChatRequest(
        message="那前面的短裤呢？我觉得也可以买一条，大概多少码合适？",
        history=[
            *history,
            ChatMessage(
                role="user",
                content="好的，我觉得阿迪达斯的不错。然后我妈是168厘米，体重是130斤，穿多大的比较合适？",
            ),
            ChatMessage(
                role="assistant",
                content="这款adidas Essentials 三条纹运动长裤，建议选L码。",
                product_ids=["p_clothes_004"],
            ),
        ],
    )
    shorts_build = build_retrieval_message(shorts_request)
    shorts_intent = parse_query_intent(shorts_build.message)
    assert shorts_intent.referenced_product_ids == ["p_clothes_023"], shorts_build.message
    assert not shorts_intent.comparison_mode


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


def check_planner_scene_bundle_plan() -> None:
    request = ChatRequest(
        message="下周去三亚度假，帮我搭配一套从防晒到穿搭的方案",
        history=[],
    )
    rule_build = build_retrieval_message(request)
    plan = RetrievalPlan.model_validate(
        {
            "turn_type": "new_search",
            "recommendation_mode": "scene_bundle",
            "rewrite_query": "三亚度假 防晒 穿搭 方案",
            "budget_update": {"type": "keep", "value": None},
            "category_patch": {"mode": "keep", "include": [], "exclude": [], "reason_type": "none"},
            "facets_patch": {},
            "search_slots": [
                {
                    "label": "防晒防护",
                    "category": "beauty",
                    "sub_categories": ["防晒"],
                    "effects": ["防晒"],
                    "use_cases": ["户外"],
                },
                {
                    "label": "海边穿搭",
                    "category": "apparel",
                    "sub_categories": ["短袖T恤", "速干T恤", "帽子", "运动短裤", "背包"],
                    "effects": [],
                    "use_cases": ["户外"],
                },
            ],
            "exclude_terms_patch": [],
            "referenced_product_policy": "none",
            "needs_clarification": False,
            "clarification_question": None,
            "confidence": 0.92,
        }
    )
    validated, additions, errors = _validate_plan(plan, request, rule_build)
    assert not errors, errors
    assert validated["recommendation_mode"] == "scene_bundle"
    assert "- 推荐模式：场景组合" in additions
    assert "- 类目：美妆护肤、服饰运动" in additions
    merged = _append_planner_additions(rule_build.message, additions, request.message)
    intent = parse_query_intent(merged)
    assert intent.category_candidates == ["beauty", "apparel"], merged
    assert "防晒" in intent.facets.get("sub_category", []), merged
    assert "帽子" in intent.facets.get("sub_category", []), merged


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
    assert trace["fallback_reason"] == "planner_disabled_by_mock_or_missing_llm_config"


if __name__ == "__main__":
    main()
