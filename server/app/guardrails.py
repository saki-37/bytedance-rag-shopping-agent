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
ABSENCE_CLAIM_TERMS = ["酒精", "刺激", "香精", "致痘", "拔干"]
ABSENCE_PREFIXES = ["不含", "无", "没有", "不会有", "不会", "不添加", "不含有"]


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

    unsupported_absence_claims = _unsupported_absence_claims(stripped, cards)
    if unsupported_absence_claims:
        issues.append(f"unsupported_absence_claims:{','.join(unsupported_absence_claims)}")

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


def _unsupported_absence_claims(answer: str, cards: list[ProductCard]) -> list[str]:
    evidence = _card_evidence_text(cards)
    unsupported: list[str] = []
    for term in ABSENCE_CLAIM_TERMS:
        if not _claims_absence(answer, term):
            continue
        if not _evidence_supports_absence(evidence, term):
            unsupported.append(term)
    return unsupported


def _claims_absence(text: str, term: str) -> bool:
    return any(
        re.search(rf"{prefix}[^。；，,.]{{0,12}}{re.escape(term)}", text)
        for prefix in ABSENCE_PREFIXES
    )


def _evidence_supports_absence(evidence: str, term: str) -> bool:
    return any(
        re.search(rf"{prefix}[^。；，,.]{{0,12}}{re.escape(term)}", evidence)
        for prefix in ABSENCE_PREFIXES
    )


def _card_evidence_text(cards: list[ProductCard]) -> str:
    parts: list[str] = []
    for card in cards:
        parts.extend(
            [
                card.title,
                card.brand,
                card.reason,
                card.description,
                " ".join(card.tags),
                " ".join(card.target_users),
                " ".join(card.use_cases),
                " ".join(card.selling_points),
                " ".join(card.cautions),
                " ".join(card.suitable_for),
                " ".join(card.avoid_for),
            ]
        )
    return " ".join(parts)


def _extract_prices(text: str) -> list[str]:
    prices: list[str] = []
    for match in PRICE_PATTERN.finditer(text):
        raw = match.group(1) or match.group(2)
        prices.append(_normalize_price(float(raw)))
    return prices


def _normalize_price(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")
