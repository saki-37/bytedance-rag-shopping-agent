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
RESULT_ABSENCE_CLAIM_TERMS = ["堵塞", "闭口", "残留", "闷痘", "过敏"]
RESULT_BOUNDARY_TERMS = [
    "不能保证",
    "无法保证",
    "不保证",
    "不能确认",
    "无法确认",
    "不能完全排除",
    "不等于",
    "仅作为",
    "只能作为",
    "体验线索",
    "个别用户反馈",
    "建议先",
]
RESULT_REVIEW_QUALIFIERS = ["用户评价", "用户反馈", "有人提到", "有人说", "个别用户", "评论"]


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

    unsupported_result_absence_claims = _unsupported_result_absence_claims(stripped)
    if unsupported_result_absence_claims:
        issues.append(f"unsupported_result_absence_claims:{','.join(unsupported_result_absence_claims)}")

    if issues:
        return GenerationGuardrailResult(
            answer=build_safe_answer(cards, user_message=user_message),
            passed=False,
            issues=issues,
            fallback_used=True,
        )
    return GenerationGuardrailResult(answer=stripped, passed=True)


def build_safe_answer(cards: list[ProductCard], user_message: str | None = None) -> str:
    user_message = user_message or ""
    if not cards:
        if _has_specific_constraints(user_message):
            budget = _latest_budget_label(user_message)
            budget_clause = f"{budget}和这些条件" if budget else "这些条件"
            return (
                f"我读到了你前面的条件，但当前商品池里没有同时满足{budget_clause}的商品。"
                "可以先放宽预算、放宽排除条件，或把防晒和修护拆开分别看。"
            )
        return "我需要先补充一点关键信息：你的肤质、预算和主要功效需求分别是什么？"

    evidence_notes = _build_evidence_notes(cards, user_message)

    if len(cards) >= 2 and _is_comparison_request(user_message):
        answer = _build_comparison_answer(cards, user_message)
        if evidence_notes:
            answer += "\n" + "\n".join(evidence_notes)
        return answer

    if len(cards) == 1:
        card = cards[0]
        lines = [
            f"我先基于商品资料给出保守推荐：{_card_name(card)}，数据源价格 ¥{card.price:g}。",
            f"资料中可支持的匹配点：{_supported_points(card)}。",
        ]
        if card.cautions:
            lines.append(f"需要注意：{'；'.join(card.cautions[:2])}。")
        lines.extend(evidence_notes)
        lines.append("我不会补充数据源之外的商业承诺或额外功效信息。")
        return "\n".join(lines)

    lines = ["按你现在的条件，我先把能被商品资料支撑的选择收窄到这几款："]
    for index, card in enumerate(cards[:3], start=1):
        line = (
            f"{index}. {_card_name(card)}，数据源价格 ¥{card.price:g}。"
            f"{_supported_points(card)}"
        )
        if card.cautions:
            line += f" 注意：{card.cautions[0]}。"
        lines.append(line)
    lines.extend(evidence_notes)
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
    lines.append("我这里只按已召回商品资料比较，不补资料外的价格、供货、活动或额外功效。")
    return "\n".join(lines)


def _build_evidence_notes(cards: list[ProductCard], user_message: str) -> list[str]:
    evidence = _card_evidence_text(cards)
    notes: list[str] = []
    budget = _latest_budget_label(user_message)
    if budget and cards:
        budget_value = _latest_budget_value(user_message)
        if budget_value is not None:
            over_budget_cards = [card for card in cards if card.price > budget_value]
        else:
            over_budget_cards = []
        if over_budget_cards:
            over_budget_names = "、".join(_card_name(card) for card in over_budget_cards[:2])
            notes.append(
                f"预算边界：{over_budget_names}的数据源价格高于{budget}，"
                "不能说它仍在预算内；如果继续看它，需要先确认是否放宽预算。"
            )
        else:
            notes.append(f"预算边界：当前候选商品资料价格在{budget}范围内，预算之外的价格不作为推荐依据。")
    elif "预算" in user_message and cards:
        notes.append("预算边界：当前先看预算友好的候选，具体上限还可以继续确认。")

    if "水杨酸" in user_message:
        if "烟酰胺" in evidence or "锌" in evidence:
            seen = "、".join(_present_terms(evidence, ["烟酰胺", "锌"]))
            notes.append(f"成分边界：商品资料看到{seen}，未看到水杨酸；它不是水杨酸，也不能当刷酸使用。")
        elif "水杨酸" in evidence:
            notes.append("成分边界：商品资料看到水杨酸，但仍不能把它自动等同于闭口或痘痘治疗。")
        else:
            notes.append("成分边界：商品资料未看到水杨酸，所以不能确认这个成分，也不能把它当作祛痘或闭口治疗依据。")

    if _contains_any(user_message, ["PITERA", "pitera", "刷酸", "祛痘"]):
        if "PITERA" in evidence or "调理角质" in evidence:
            supported = "、".join(_present_terms(evidence, ["PITERA", "调理角质"]))
            notes.append(f"功效边界：商品资料支持{supported or '对应护肤卖点'}，但不能把它等同于刷酸或祛痘治疗。")
        else:
            notes.append("功效边界：商品资料没有足够证据支持刷酸或祛痘治疗这类外推。")

    if _contains_any(user_message, ["发酵", "不耐受", "过敏"]):
        if "发酵" in evidence:
            notes.append("风险边界：资料涉及发酵相关成分；如果你对发酵类成分不耐受，不建议直接上脸，先做局部测试。")
        else:
            notes.append("风险边界：过敏和不耐受不能只靠导购回答排除，建议先做局部测试并核对完整成分表。")

    if _contains_any(user_message, ["孕妇", "孕期", "怀孕", "不过敏", "保证"]):
        notes.append("安全边界：孕妇/孕期适用性当前资料不能确认；也不能保证不过敏，建议先做局部测试或24小时测试。")

    if _contains_any(user_message, ["酒精", "香精", "防腐剂", "刺激"]):
        supported_absence = _supported_absence_terms(evidence, ["酒精", "香精", "防腐剂"])
        if supported_absence:
            if "FANCL" in evidence or "芳珂" in evidence:
                notes.append(f"无添加证据：商品资料明确写到{'、'.join(supported_absence)}，但敏感肌仍建议先做局部测试。")
            else:
                notes.append(f"排除条件：商品资料明确写到{'、'.join(supported_absence)}；敏感肌仍建议先做局部测试或24小时测试。")
        else:
            notes.append("排除条件：我会仍然保留酒精、刺激这类边界；资料未明确写到时，不断言没有相关风险。")

    if _contains_any(user_message, ["预算放", "预算可以", "放宽预算", "放到300"]):
        if _contains_any(user_message, ["酒精", "刺激"]):
            notes.append("多轮边界：这轮只放宽预算，仍然保留酒精和刺激排除条件。")

    if "闭口" in user_message and _contains_any(evidence, ["修护", "屏障", "保湿"]):
        notes.append("功效边界：资料支持修护屏障或保湿方向，但不能把它说成闭口治疗。")

    if _contains_any(user_message, ["一起用", "叠加", "更快"]):
        notes.append("使用边界：不能保证更快；建议先建立耐受，避免刺激，再逐步叠加。")

    if _contains_any(user_message, ["用户评价", "有人说", "有人这么说", "小红书", "评论", "孕期"]):
        notes.append("来源边界：用户评价只能当体验线索，不能等同于官方成分或安全承诺。")

    if "堵塞" in user_message:
        notes.append("来源边界：如果资料里出现“不堵塞”等说法，也只能作为用户反馈，不能保证你使用后一定不堵塞。")

    if "购买链接" in user_message:
        notes.append("商业信息边界：当前资料没有购买链接或优惠信息，我不能补数据源之外的商业信息。")
    elif _contains_any(user_message, ["优惠", "活动", "下单", "购买建议"]):
        notes.append("商业信息边界：当前资料没有活动或供货信息，我不能补数据源之外的商业信息。")

    if _contains_any(user_message, ["总结", "怎么买"]) and _contains_any(user_message + evidence, ["控油", "提亮", "修护", "屏障"]):
        notes.append("总结边界：按当前商品资料，可以把控油提亮和修护屏障分成两个方向；但不能保证更快或额外治疗效果。")

    if _contains_any(user_message, ["不知道怎么选", "怎么选"]) and not (
        budget or _contains_any(user_message, ["油皮", "干皮", "敏感肌", "通勤", "户外"])
    ):
        notes.append("澄清边界：更稳的推荐还需要确认肤质、预算和使用场景。")

    return _dedupe_notes(notes)


def _card_name(card: ProductCard) -> str:
    if card.brand and card.title:
        return f"{card.brand}｜{card.title}"
    return card.brand or card.title


def _supported_points(card: ProductCard) -> str:
    points: list[str] = []
    points.extend(card.selling_points[:2])
    points.extend(card.use_cases[:2])
    points.extend(card.suitable_for[:2])
    if card.reason:
        points.append(card.reason)
    points.extend(card.tags[:3])
    points = _dedupe_notes([point for point in points if point])
    return "；".join(points[:6]) or "商品资料里有对应匹配点"


def _latest_budget_label(text: str) -> str | None:
    value = _latest_budget_value(text)
    if value is None:
        return None
    normalized = f"{value:g}"
    return f"{normalized}元以内"


def _latest_budget_value(text: str) -> float | None:
    matches = list(re.finditer(r"(\d+(?:\.\d+)?)\s*元?\s*(?:以[内下]|以内|以下|之内|内)", text))
    direct_budget_matches = list(
        re.finditer(
            r"预算[^。；，,.]{0,12}(?:降到|压到|改到|放宽到|控制在|不超过|最多|上限|到|为)\s*(\d+(?:\.\d+)?)\s*元?",
            text,
        )
    )
    matches.extend(direct_budget_matches)
    if not matches:
        return None
    matches.sort(key=lambda match: match.start())
    return float(matches[-1].group(1))


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _present_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in text]


def _supported_absence_terms(evidence: str, terms: list[str]) -> list[str]:
    supported: list[str] = []
    for term in terms:
        if _evidence_supports_absence(evidence, term):
            supported.append(f"不含{term}/无{term}")
    return supported


def _dedupe_notes(notes: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for note in notes:
        compact = note.strip()
        if not compact or compact in seen:
            continue
        seen.add(compact)
        deduped.append(compact)
    return deduped


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


def _unsupported_result_absence_claims(answer: str) -> list[str]:
    unsupported: list[str] = []
    for term in RESULT_ABSENCE_CLAIM_TERMS:
        claim_segments = _result_absence_claim_segments(answer, term)
        if any(not _result_claim_is_bounded(segment) for segment in claim_segments):
            unsupported.append(term)
    if any(phrase in answer for phrase in ["绝对温和", "一定安全", "完全安全", "放心使用", "放心用"]):
        if not _result_claim_is_bounded(answer):
            unsupported.append("absolute_safety")
    return list(dict.fromkeys(unsupported))


def _result_absence_claim_segments(text: str, term: str) -> list[str]:
    segments = _claim_segments(text)
    claim_segments: list[str] = []
    for segment in segments:
        if _claims_result_absence(segment, term):
            claim_segments.append(segment)
    return claim_segments


def _claims_result_absence(text: str, term: str) -> bool:
    patterns = [
        rf"(不会|不容易|不太会|不用担心|正常使用不会|保证不|一定不|绝对不)[^。；，,.]{{0,16}}{re.escape(term)}",
        rf"(不|无|没有)[^。；，,.]{{0,8}}{re.escape(term)}",
        rf"{re.escape(term)}[^。；，,.]{{0,12}}(不会|不用担心|风险低|没问题)",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _result_claim_is_bounded(segment: str) -> bool:
    if any(term in segment for term in RESULT_BOUNDARY_TERMS):
        return True
    return any(qualifier in segment for qualifier in RESULT_REVIEW_QUALIFIERS)


def _claim_segments(text: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"[。；;.!?？\n]", text) if segment.strip()]


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
