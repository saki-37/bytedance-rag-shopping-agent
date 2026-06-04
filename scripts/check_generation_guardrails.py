#!/usr/bin/env python3
"""Check that generated text stays bound to retrieved product evidence."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.config import get_settings
from app.data_loader import load_enriched_products, load_raw_products
from app.guardrails import guard_answer
from app.retrieval import retrieve


def main() -> None:
    settings = get_settings()
    raw_products = load_raw_products(settings.raw_data_dir)
    products = load_enriched_products(settings.enriched_data_dir, raw_products)
    result = retrieve("我是油皮，想要 200 元以内的通勤防晒", products, index_dir=settings.index_dir)
    cards = result.cards

    safe = guard_answer(
        "推荐巴黎欧莱雅，数据源价格 ¥170，适合通勤防晒，敏感肌先做耳后测试。",
        user_message="我是油皮，想要 200 元以内的通勤防晒",
        cards=cards,
    )
    assert safe.passed, safe
    assert not safe.fallback_used, safe

    unsafe = guard_answer(
        "推荐巴黎欧莱雅，价格 ¥199，库存充足，还有优惠券，下单很划算。",
        user_message="我是油皮，想要 200 元以内的通勤防晒",
        cards=cards,
    )
    assert not unsafe.passed, unsafe
    assert unsafe.fallback_used, unsafe
    assert "库存" not in unsafe.answer and "优惠券" not in unsafe.answer, unsafe.answer
    assert "¥199" not in unsafe.answer, unsafe.answer

    unsupported_absence = guard_answer(
        "这款粉底不会有过重的酒精味和强烈刺激感。",
        user_message="不要酒精味太重或者刺激感强的产品",
        cards=cards,
    )
    assert not unsupported_absence.passed, unsupported_absence
    assert unsupported_absence.fallback_used, unsupported_absence
    assert "unsupported_absence_claims" in ",".join(unsupported_absence.issues), unsupported_absence.issues

    cleansing_oil = retrieve("敏感肌卸妆油，不要堵塞毛孔", products, index_dir=settings.index_dir)
    result_absence = guard_answer(
        "这款卸妆油正常使用不会堵塞毛孔，也不会长闭口，可以放心使用。",
        user_message="它是不是能深入毛孔，而且不会堵塞？",
        cards=cleansing_oil.cards,
    )
    assert not result_absence.passed, result_absence
    assert result_absence.fallback_used, result_absence
    assert "unsupported_result_absence_claims" in ",".join(result_absence.issues), result_absence.issues

    qualified_result_absence = guard_answer(
        "商品资料写到纳米级卸妆分子可以包裹彩妆和污垢，用户评价里有人提到不会堵塞；但这只能作为体验线索，不能保证你使用后也一定如此。",
        user_message="它是不是能深入毛孔，而且不会堵塞？",
        cards=cleansing_oil.cards,
    )
    assert qualified_result_absence.passed, qualified_result_absence

    over_budget_reference = retrieve("我想把预算降到150元，那欧莱雅能保证不过敏吗？", products, index_dir=settings.index_dir)
    over_budget_fallback = guard_answer(
        "",
        user_message="我想把预算降到150元，那欧莱雅能保证不过敏吗？",
        cards=over_budget_reference.cards,
    )
    assert over_budget_fallback.fallback_used, over_budget_fallback
    assert "价格高于150元以内" in over_budget_fallback.answer, over_budget_fallback.answer
    assert "价格在150元以内范围内" not in over_budget_fallback.answer, over_budget_fallback.answer

    empty = guard_answer("", user_message="我想买护肤品", cards=[])
    assert not empty.passed, empty
    assert empty.fallback_used, empty
    assert "肤质" in empty.answer, empty.answer

    constrained_empty = guard_answer(
        "",
        user_message=(
            "我是油皮，想要200元以内通勤防晒。"
            "敏感肌最近屏障不稳定，想找修护面霜。"
            "不要酒精味太重或者刺激感强的产品。"
        ),
        cards=[],
    )
    assert not constrained_empty.passed, constrained_empty
    assert constrained_empty.fallback_used, constrained_empty
    assert "我读到了你前面的条件" in constrained_empty.answer, constrained_empty.answer
    assert "肤质、预算和主要功效需求分别是什么" not in constrained_empty.answer, constrained_empty.answer

    print("Generation guardrails OK")


if __name__ == "__main__":
    main()
