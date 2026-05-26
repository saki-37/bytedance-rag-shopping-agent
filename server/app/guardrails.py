import re
from dataclasses import dataclass, field

from app.models import ProductCard


FORBIDDEN_COMMERCIAL_CLAIMS = [
    "库存",
    "现货",
    "优惠",
    "优惠券",
    "满减",
    "折扣",
    "下单",
    "购买链接",
    "销量",
]

PRICE_PATTERN = re.compile(r"(?:[¥￥]\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*元)")


@dataclass
class GenerationGuardrailResult:
    answer: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    fallback_used: bool = False


def guard_answer(answer: str, user_message: str, cards: list[ProductCard]) -> GenerationGuardrailResult:
    issues: list[str] = []
    stripped = answer.strip()
    if not stripped:
        issues.append("empty_answer")

    forbidden_terms = [term for term in FORBIDDEN_COMMERCIAL_CLAIMS if term in stripped]
    if forbidden_terms:
        issues.append(f"forbidden_commercial_claims:{','.join(forbidden_terms)}")

    unsupported_prices = _unsupported_prices(stripped, user_message, cards)
    if unsupported_prices:
        issues.append(f"unsupported_prices:{','.join(unsupported_prices)}")

    if issues:
        return GenerationGuardrailResult(
            answer=build_safe_answer(cards),
            passed=False,
            issues=issues,
            fallback_used=True,
        )
    return GenerationGuardrailResult(answer=stripped, passed=True)


def build_safe_answer(cards: list[ProductCard]) -> str:
    if not cards:
        return "我需要先补充一点关键信息：你的肤质、预算和主要功效需求分别是什么？"

    lines = [
        "我先基于已召回的商品资料给出保守推荐，价格、品牌和注意事项都来自数据源：",
    ]
    for index, card in enumerate(cards[:3], start=1):
        reason = card.reason or "与本次需求有匹配点。"
        cautions = "；".join(card.cautions[:2])
        caution_text = f" 注意事项：{cautions}。" if cautions else ""
        lines.append(
            f"{index}. {card.brand}｜{card.title}，数据源价格 ¥{card.price:g}。"
            f"推荐理由：{reason}{caution_text}"
        )
    lines.append("我不会补充数据源之外的商业承诺或额外功效信息。")
    return "\n".join(lines)


def _unsupported_prices(answer: str, user_message: str, cards: list[ProductCard]) -> list[str]:
    allowed = {_normalize_price(card.price) for card in cards}
    allowed.update(_extract_prices(user_message))
    return [price for price in _extract_prices(answer) if price not in allowed]


def _extract_prices(text: str) -> list[str]:
    prices: list[str] = []
    for match in PRICE_PATTERN.finditer(text):
        raw = match.group(1) or match.group(2)
        prices.append(_normalize_price(float(raw)))
    return prices


def _normalize_price(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")
