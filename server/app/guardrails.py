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
            answer=build_safe_answer(cards, user_message=user_message),
            passed=False,
            issues=issues,
            fallback_used=True,
        )
    return GenerationGuardrailResult(answer=stripped, passed=True)


def build_safe_answer(cards: list[ProductCard], user_message: str | None = None) -> str:
    if not cards:
        if user_message and _has_specific_constraints(user_message):
            return (
                "我读到了你前面的条件，但当前商品池里没有足够证据支撑一个可靠推荐。"
                "可以先放宽预算或排除条件；如果你愿意，我也可以把防晒和修护拆开分别看。"
            )
        return "我需要先补充一点关键信息：你的肤质、预算和主要功效需求分别是什么？"

    if len(cards) >= 2 and user_message and _is_comparison_request(user_message):
        return _build_comparison_answer(cards, user_message)

    if len(cards) == 1:
        card = cards[0]
        lines = [
            f"按你现在给的条件，我会先看这一个更稳的选择：{card.brand}，¥{card.price:g}。",
            f"它和需求的匹配点是：{card.reason or '商品资料里有对应匹配点。'}",
        ]
        if card.cautions:
            lines.append(f"需要注意：{'；'.join(card.cautions[:2])}。")
        lines.append("我这里只按商品资料说，不补资料外的商业承诺或额外功效。")
        return "\n".join(lines)

    lines = ["按你现在的条件，我先把能被商品资料支撑的选择收窄到这几款："]
    for index, card in enumerate(cards[:3], start=1):
        reason = card.reason or "商品资料里有对应匹配点。"
        line = f"{index}. {card.brand}，¥{card.price:g}。{reason}"
        if card.cautions:
            line += f" 注意：{card.cautions[0]}。"
        lines.append(line)
    lines.append("上面只使用已召回商品资料，暂时不补资料外的商业承诺或额外功效。")
    return "\n".join(lines)


def _build_comparison_answer(cards: list[ProductCard], user_message: str) -> str:
    lines = ["我先按商品资料做一个保守对比："]
    for index, card in enumerate(cards[:3], start=1):
        fit = "、".join(card.suitable_for[:2] or card.target_users[:2] or card.use_cases[:2])
        caution = "；".join(card.cautions[:1] or card.avoid_for[:1])
        parts = [
            f"{index}. {card.brand}｜¥{card.price:g}",
            f"适合：{fit or '资料中主要匹配本次需求'}",
            f"理由：{card.reason or '商品资料里有对应匹配点'}",
        ]
        if caution:
            parts.append(f"注意：{caution}")
        lines.append("；".join(parts) + "。")

    best = cards[0]
    lines.append(
        f"如果只能先选一个，我会先看 {best.brand}：它在当前检索里和你的问题匹配更靠前；"
        "但最终仍要按你的预算、场景和不能接受的风险来定。"
    )
    lines.append("我这里只按已召回商品资料比较，不补资料外的价格、库存、优惠或额外功效。")
    return "\n".join(lines)


def _unsupported_prices(answer: str, user_message: str, cards: list[ProductCard]) -> list[str]:
    allowed = {_normalize_price(card.price) for card in cards}
    allowed.update(_extract_prices(user_message))
    return [price for price in _extract_prices(answer) if price not in allowed]


def _unsupported_absence_claims(answer: str, cards: list[ProductCard]) -> list[str]:
    relevant_cards = _mentioned_cards(answer, cards) or cards
    unsupported: list[str] = []
    for term in ABSENCE_CLAIM_TERMS:
        if not _claims_absence(answer, term):
            continue
        if not relevant_cards or not all(
            _evidence_supports_absence(_card_evidence_text([card]), term)
            for card in relevant_cards
        ):
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


def _mentioned_cards(answer: str, cards: list[ProductCard]) -> list[ProductCard]:
    mentioned: list[ProductCard] = []
    for card in cards:
        if card.brand and card.brand in answer:
            mentioned.append(card)
            continue
        compact_title = card.title[:12]
        if compact_title and compact_title in answer:
            mentioned.append(card)
    return mentioned


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


def _has_specific_constraints(user_message: str) -> bool:
    if re.search(r"\d+(?:\.\d+)?\s*元?\s*(?:以[内下]|以内|以下|之内|内)", user_message):
        return True
    return any(
        term in user_message
        for term in [
            "油皮",
            "干皮",
            "敏感",
            "屏障",
            "防晒",
            "修护",
            "控油",
            "保湿",
            "提亮",
            "抗初老",
            "底妆",
            "面霜",
            "精华",
            "不要",
            "避开",
            "不含",
            "酒精",
            "刺激",
        ]
    )


def _is_comparison_request(user_message: str) -> bool:
    return any(
        term in user_message
        for term in [
            "对比",
            "比较",
            "怎么选",
            "选哪个",
            "买哪个",
            "该买哪个",
            "哪个更",
            "哪款更",
            "更适合",
            "二选一",
            "区别",
        ]
    )


def _extract_prices(text: str) -> list[str]:
    prices: list[str] = []
    for match in PRICE_PATTERN.finditer(text):
        raw = match.group(1) or match.group(2)
        prices.append(_normalize_price(float(raw)))
    return prices


def _normalize_price(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")
