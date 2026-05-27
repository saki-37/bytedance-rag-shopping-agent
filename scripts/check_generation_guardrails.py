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
    products = load_enriched_products(settings.enriched_beauty_path, raw_products)
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
