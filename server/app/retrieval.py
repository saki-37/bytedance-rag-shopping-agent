import contextlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

from app.data_loader import CATEGORY_TO_CANONICAL, product_search_text
from app.embeddings import sentence_model
from app.models import (
    FilteredProduct,
    GuardrailChecks,
    ProductCard,
    QueryIntent,
    RetrievalChannels,
    RetrievalHit,
    RetrievalTrace,
    UniversalConstraints,
)


@dataclass
class RetrievalResult:
    cards: list[ProductCard]
    context: str
    trace: RetrievalTrace
    clarification_question: str | None = None


FACET_LEXICON: dict[str, dict[str, list[str]]] = {
    "skin_type": {
        "油皮": ["油皮", "大油皮", "混油", "混油皮", "出油"],
        "干皮": ["干皮", "混干", "混干皮", "干燥"],
        "敏感肌": ["敏感肌", "敏感", "屏障", "泛红", "刺痛"],
    },
    "effect": {
        "防晒": ["防晒", "spf", "pa", "晒黑", "晒伤"],
        "修护": ["修护", "屏障", "舒缓", "维稳"],
        "保湿": ["保湿", "补水", "滋润", "干燥"],
        "控油": ["控油", "油脂", "出油", "清爽"],
        "提亮": ["提亮", "亮肤", "美白", "暗沉"],
        "淡斑": ["淡斑", "斑点", "色斑", "痘印", "色沉", "色素"],
        "抗初老": ["抗初老", "抗老", "淡纹", "紧致", "抗皱"],
        "清洁": ["清洁", "毛孔污垢"],
        "洁面": ["洁面", "洗面奶", "泡沫洁面"],
        "卸妆": ["卸妆", "卸除", "防水彩妆"],
        "眼周护理": ["眼霜", "眼周", "干纹", "卡粉"],
        "底妆": ["底妆", "粉底", "粉底液", "遮瑕"],
        "定妆": ["定妆", "蜜粉", "散粉", "持妆"],
        "唇妆": ["唇釉", "口红", "唇妆", "显色", "沾杯"],
        "眉妆": ["眉笔", "画眉", "眉妆", "眉尾", "野生眉"],
    },
    "use_case": {
        "通勤": ["通勤", "上班", "日常"],
        "户外": ["户外", "海边", "爬山", "旅行", "三亚"],
        "运动": ["运动", "跑步", "健身", "防汗"],
        "妆前": ["妆前", "打底", "上妆"],
        "夜间": ["夜间", "晚上", "睡前"],
        "约会": ["约会", "聚会", "拍照", "妆造"],
        "出差": ["出差", "旅行装", "便携", "随身"],
    },
    "sub_category": {
        "防晒": ["防晒", "防晒霜"],
        "面霜": ["面霜", "霜", "特护霜"],
        "精华": ["精华", "精华液"],
        "卸妆": ["卸妆", "卸妆油"],
        "洁面": ["洁面", "洗面奶", "泡沫洁面"],
        "眼霜": ["眼霜"],
        "蜜粉": ["蜜粉", "散粉"],
        "唇釉": ["唇釉", "口红"],
        "眉笔": ["眉笔"],
        "短袖T恤": ["短袖", "T恤", "t恤", "白T", "基础T", "速干衣"],
        "跑步鞋": ["跑步鞋", "慢跑鞋", "公路跑鞋", "缓震跑鞋"],
        "徒步鞋": ["徒步鞋", "登山鞋", "防水鞋", "户外鞋"],
        "背包": ["背包", "双肩包", "电脑包", "通勤包"],
    },
}

BEAUTY_TERMS = [
    "美妆",
    "护肤",
    "护肤品",
    "化妆品",
    "防晒",
    "面霜",
    "精华",
    "粉底",
    "底妆",
    "化妆水",
    "爽肤水",
    "洗面奶",
    "洁面",
    "卸妆",
    "定妆",
    "眼霜",
    "唇釉",
    "眉笔",
    "面膜",
    "蜜粉",
    "散粉",
]
APPAREL_TERMS = [
    "服饰",
    "衣服",
    "短袖",
    "t恤",
    "T恤",
    "白T",
    "速干",
    "棉感",
    "纯棉",
    "尺码",
    "版型",
    "跑步鞋",
    "慢跑鞋",
    "徒步鞋",
    "登山鞋",
    "防水鞋",
    "抓地",
    "背包",
    "双肩包",
    "电脑包",
]
CATEGORY_TO_RAW = {
    "beauty": "美妆护肤",
    "apparel": "服饰运动",
}

GENERIC_RECOMMEND_TERMS = ["推荐", "买什么", "护肤品", "化妆品", "随便", "看看"]
EXCLUDE_TERMS = ["酒精", "香精", "刺激", "刺痛", "太油", "油腻", "厚重", "拔干", "日系"]
SOFT_PREFERENCE_TERMS = [
    "便宜",
    "清爽",
    "轻薄",
    "温和",
    "自然",
    "滋润",
    "高倍",
    "防水",
    "防汗",
    "便携",
    "持久",
    "显色",
    "不沾杯",
    "不晕染",
    "防晕染",
]
COMPARISON_TERMS = [
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
    "还是",
    "区别",
]


def _query_terms(query: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{1,4}", query):
        token = token.strip().lower()
        if token:
            terms.add(token)
    return terms


def parse_query_intent(query: str) -> QueryIntent:
    referenced_product_ids = _extract_referenced_product_ids(query)
    budget = None if _relaxes_budget(query) else _hard_budget(query)
    facets = _extract_facets(query)
    exclude_terms = [] if _relaxes_exclusions(query) else _extract_exclude_terms(query)
    soft_preferences = _extract_soft_preferences(query)
    comparison_mode = _is_comparison_query(query)
    category_candidates = _extract_category_candidates(query, facets, exclude_terms)
    hard_constraints: list[str] = []
    if budget is not None:
        hard_constraints.append(f"budget_max <= {budget:g}")
    hard_constraints.extend(f"referenced_product:{product_id}" for product_id in referenced_product_ids)
    hard_constraints.extend(f"exclude:{term}" for term in exclude_terms)

    signal_count = (
        len(referenced_product_ids)
        + len(exclude_terms)
        + len(soft_preferences)
        + sum(len(values) for values in facets.values())
        + (1 if budget is not None else 0)
    )
    needs_clarification = _needs_clarification(query, signal_count)
    confidence = min(0.95, 0.2 + signal_count * 0.15 + (0.1 if category_candidates else 0.0))
    return QueryIntent(
        category_candidates=category_candidates,
        referenced_product_ids=referenced_product_ids,
        universal_constraints=UniversalConstraints(budget_max=budget),
        facets=facets,
        hard_constraints=hard_constraints,
        soft_preferences=soft_preferences,
        exclude_terms=exclude_terms,
        comparison_mode=comparison_mode,
        needs_clarification=needs_clarification,
        clarification_question=(
            "你更在意肤质、预算，还是防晒/修护/控油这类具体功效？"
            if needs_clarification
            else None
        ),
        confidence=round(confidence, 2),
    )


def _hard_budget(query: str) -> float | None:
    patterns = [
        r"(\d+(?:\.\d+)?)\s*元?\s*(?:以[内下]|以内|以下|之内|内)",
        r"(?:预算|价格|价位).{0,8}(?:放宽到|放宽至|放到|放至|调高到|调高至|提高到|提高至)\s*(\d+(?:\.\d+)?)\s*元?",
        r"(?:预算|价格|价位)\s*(?:降到|降至|降低到|压到|压低到|控制在|调到|改成|设成|缩到)\s*(\d+(?:\.\d+)?)\s*元?",
        r"(?:放宽到|放宽至|放到|放至|调高到|调高至|提高到|提高至)\s*(\d+(?:\.\d+)?)\s*元?",
        r"(?:预算|价格|价位)\s*(?:在|不超过|别超过|低于|小于|不高于|<=)?\s*(\d+(?:\.\d+)?)",
        r"(?:降到|降至|降低到|压到|压低到|控制在|调到|改成|设成|缩到)\s*(\d+(?:\.\d+)?)\s*元?",
        r"(?:不超过|别超过|低于|小于|不高于|<=)\s*(\d+(?:\.\d+)?)\s*元?",
    ]
    matches: list[tuple[int, float]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, query):
            matches.append((match.start(), float(match.group(1))))
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def _extract_referenced_product_ids(query: str) -> list[str]:
    ids = re.findall(r"\bp_[a-z]+_\d+\b", query)
    return list(dict.fromkeys(ids))


def _relaxes_budget(query: str) -> bool:
    if _hard_budget(query) is not None:
        return False
    return bool(
        re.search(
            r"(放宽|不限制|先不看|先不用管|可以超过|不限).{0,8}(预算|价格|价位)",
            query,
        )
        or re.search(r"(预算|价格|价位).{0,8}(放宽|不限制|先不看|先不用管|可以超过|不限)", query)
    )


def _relaxes_exclusions(query: str) -> bool:
    if _extract_exclude_terms(query):
        return False
    return bool(
        re.search(
            r"(放宽|先不看|先不用管|可以接受).{0,8}(排除|避开|成分)",
            query,
        )
        or re.search(r"(排除|避开|酒精|刺激|成分).{0,8}(放宽|先不看|先不用管|可以接受)", query)
    )


def _extract_facets(query: str) -> dict[str, list[str]]:
    facets: dict[str, list[str]] = {}
    query_lower = query.lower()
    for facet_name, values in FACET_LEXICON.items():
        matched: list[str] = []
        for canonical, synonyms in values.items():
            if any(synonym.lower() in query_lower for synonym in synonyms):
                matched.append(canonical)
        if matched:
            facets[facet_name] = matched
    return facets


def _extract_exclude_terms(query: str) -> list[str]:
    terms: list[str] = []
    for term in EXCLUDE_TERMS:
        if term in query and (
            re.search(rf"(不要|不想|不含|避开|排除|别太|不能).*{re.escape(term)}", query)
            or re.search(rf"{re.escape(term)}[^。；，,.]{{0,12}}(不要|不想|不行|避开|排除|别太|不能|还是不要)", query)
        ):
            terms.append(term)
    return list(dict.fromkeys(terms))


def _extract_soft_preferences(query: str) -> list[str]:
    return [term for term in SOFT_PREFERENCE_TERMS if term in query]


def _is_comparison_query(query: str) -> bool:
    return any(term in query for term in COMPARISON_TERMS)


def _extract_category_candidates(
    query: str,
    facets: dict[str, list[str]],
    exclude_terms: list[str],
) -> list[str]:
    candidates: list[str] = []
    if _looks_like_beauty_query(query, facets) or exclude_terms:
        candidates.append("beauty")
    if _looks_like_apparel_query(query):
        candidates.append("apparel")
    return candidates


def _looks_like_beauty_query(query: str, facets: dict[str, list[str]]) -> bool:
    if any(term in query for term in BEAUTY_TERMS):
        return True
    return any(key in facets for key in ["skin_type", "effect"])


def _looks_like_apparel_query(query: str) -> bool:
    return any(term in query for term in APPAREL_TERMS)


def _needs_clarification(query: str, signal_count: int) -> bool:
    if signal_count > 0:
        return False
    return any(term in query for term in GENERIC_RECOMMEND_TERMS)


def retrieve(query: str, products: list[dict], limit: int = 3, index_dir: Path | None = None) -> RetrievalResult:
    intent = parse_query_intent(query)
    _apply_catalog_product_references(intent, query, products)
    if intent.needs_clarification:
        trace = RetrievalTrace(
            query=query,
            parsed_intent=intent,
            guardrail_checks=GuardrailChecks(needs_clarification=True),
        )
        return RetrievalResult(
            cards=[],
            context="信息不足，先追问关键条件，不进入普通推荐。",
            trace=trace,
            clarification_question=intent.clarification_question,
        )

    budget = intent.universal_constraints.budget_max
    terms = _query_terms(query)
    vector_scores, vector_hits, metadata_filter = _vector_scores(query, index_dir, intent)
    keyword_hits: list[RetrievalHit] = []
    graph_hits: list[RetrievalHit] = []
    final_hits: list[RetrievalHit] = []
    hard_filtered_out: list[FilteredProduct] = []
    scored: list[tuple[float, dict, list[str]]] = []

    for item in products:
        raw = item["raw"]
        is_referenced_product = raw["product_id"] in intent.referenced_product_ids
        if intent.referenced_product_ids and not is_referenced_product:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"product_id {raw['product_id']} not in {intent.referenced_product_ids}")
            )
            continue
        if not is_referenced_product and intent.category_candidates and not _matches_category_candidate(raw.get("category", ""), intent.category_candidates):
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"category {raw.get('category', '')} not in {intent.category_candidates}")
            )
            continue
        required_sub_categories = intent.facets.get("sub_category", [])
        if not is_referenced_product and required_sub_categories and raw.get("sub_category", "") not in required_sub_categories:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"sub_category {raw.get('sub_category', '')} not in {required_sub_categories}")
            )
            continue
        if not is_referenced_product and budget is not None and float(raw["base_price"]) > budget:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"price {raw['base_price']} > budget {budget:g}")
            )
            continue
        excluded_term = _matched_exclude_term(intent.exclude_terms, item)
        if not is_referenced_product and excluded_term is not None:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"matches excluded term: {excluded_term}")
            )
            continue
        missing_effect = _missing_required_effect(intent, item)
        if not is_referenced_product and missing_effect is not None:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"missing required effect: {missing_effect}")
            )
            continue
        text = product_search_text(item).lower()
        score = 0.0
        reasons: list[str] = []
        if is_referenced_product:
            score += 20.0
            reasons.append("referenced_product")
        keyword_score = sum(1 for term in terms if len(term) >= 2 and term.lower() in text)
        if keyword_score:
            score += keyword_score
            reasons.append(f"keyword_match:{keyword_score:g}")
            keyword_hits.append(RetrievalHit(product_id=raw["product_id"], score=float(keyword_score), reasons=["keyword_match"]))
        facet_score, facet_reasons = _facet_score(intent, item)
        score += facet_score
        reasons.extend(facet_reasons)
        graph_score, graph_reasons = _graph_score(intent, item)
        if graph_score:
            score += graph_score
            reasons.extend(graph_reasons)
            graph_hits.append(
                RetrievalHit(
                    product_id=raw["product_id"],
                    score=round(graph_score, 3),
                    reasons=graph_reasons,
                )
            )
        if raw["product_id"] in vector_scores:
            vector_score = vector_scores[raw["product_id"]]
            score += vector_score
            reasons.append(f"vector_hit:{vector_score:g}")
        if budget is not None:
            score += 1.0
            reasons.append("budget_match")
        if score > 0:
            scored.append((score, item, reasons))

    if not scored:
        scored = [
            (0.1, item, ["fallback_after_hard_filters"])
            for item in products
            if not _is_hard_filtered(item, hard_filtered_out)
        ]
    if not scored:
        trace = RetrievalTrace(
            query=query,
            parsed_intent=intent,
            metadata_filter=metadata_filter,
            hard_filtered_out=hard_filtered_out,
            filter_summary=_filter_summary(hard_filtered_out),
            retrieval_channels=RetrievalChannels(
                keyword=sorted(keyword_hits, key=lambda hit: hit.score, reverse=True)[:8],
                vector=vector_hits,
                graph=sorted(graph_hits, key=lambda hit: hit.score, reverse=True)[:8],
            ),
            guardrail_checks=GuardrailChecks(
                over_budget_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("price")),
                excluded_term_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("matches excluded")),
                needs_clarification=True,
            ),
        )
        return RetrievalResult(
            cards=[],
            context="硬约束过滤后没有可推荐商品。",
            trace=trace,
            clarification_question=_no_result_clarification(intent),
        )

    scored.sort(key=lambda pair: (pair[0], -float(pair[1]["raw"]["base_price"])), reverse=True)
    selected = [item for _, item, _ in scored[:limit]]
    final_hits = [
        RetrievalHit(product_id=item["raw"]["product_id"], score=round(score, 3), reasons=reasons)
        for score, item, reasons in scored[:limit]
    ]

    cards = [_to_card(item, query) for item in selected]
    context = "\n\n".join(_context_block(item) for item in selected)
    trace = RetrievalTrace(
        query=query,
        parsed_intent=intent,
        metadata_filter=metadata_filter,
        hard_filtered_out=hard_filtered_out,
        filter_summary=_filter_summary(hard_filtered_out),
        retrieval_channels=RetrievalChannels(
            keyword=sorted(keyword_hits, key=lambda hit: hit.score, reverse=True)[:8],
            vector=vector_hits,
            graph=sorted(graph_hits, key=lambda hit: hit.score, reverse=True)[:8],
        ),
        final_ranking=final_hits,
        ranking_signals=_ranking_signals(final_hits),
        guardrail_checks=GuardrailChecks(
            over_budget_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("price")),
            excluded_term_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("matches excluded")),
            needs_clarification=False,
        ),
    )
    return RetrievalResult(cards=cards, context=context, trace=trace)


def _apply_catalog_product_references(intent: QueryIntent, query: str, products: list[dict]) -> None:
    if intent.referenced_product_ids:
        return
    matched_ids = _catalog_product_references(query, products)
    if not matched_ids:
        return
    intent.referenced_product_ids = matched_ids
    intent.hard_constraints.extend(f"referenced_product:{product_id}" for product_id in matched_ids)
    intent.needs_clarification = False
    intent.clarification_question = None
    intent.confidence = max(intent.confidence, 0.85)


def _catalog_product_references(query: str, products: list[dict]) -> list[str]:
    normalized_query = _normalize_alias_text(query)
    if not normalized_query:
        return []
    matches: list[str] = []
    for item in products:
        raw = item["raw"]
        aliases = _product_aliases(raw)
        if any(alias and alias in normalized_query for alias in aliases):
            matches.append(raw["product_id"])
    return list(dict.fromkeys(matches))


def _product_aliases(raw: dict) -> list[str]:
    brand = str(raw.get("brand", "")).strip()
    title = str(raw.get("title", "")).strip()
    aliases = {_normalize_alias_text(brand)}
    if brand.startswith("巴黎") and len(brand) > 2:
        aliases.add(_normalize_alias_text(brand.removeprefix("巴黎")))
    if brand and title.startswith(brand):
        short_title = title[len(brand) : len(brand) + 8]
        aliases.add(_normalize_alias_text(short_title))
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", title):
        normalized_token = _normalize_alias_text(token)
        if len(normalized_token) >= 4:
            aliases.add(normalized_token)
    return [alias for alias in aliases if len(alias) >= 2]


def _normalize_alias_text(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _filter_summary(filtered: list[FilteredProduct]) -> dict[str, int]:
    counts = {
        "category": 0,
        "sub_category": 0,
        "budget": 0,
        "exclude_terms": 0,
        "required_effect": 0,
        "referenced_product": 0,
        "other": 0,
    }
    for entry in filtered:
        reason = entry.reason
        if reason.startswith("category"):
            counts["category"] += 1
        elif reason.startswith("sub_category"):
            counts["sub_category"] += 1
        elif reason.startswith("price"):
            counts["budget"] += 1
        elif reason.startswith("matches excluded"):
            counts["exclude_terms"] += 1
        elif reason.startswith("missing required effect"):
            counts["required_effect"] += 1
        elif reason.startswith("product_id"):
            counts["referenced_product"] += 1
        else:
            counts["other"] += 1
    return {key: value for key, value in counts.items() if value}


def _ranking_signals(final_hits: list[RetrievalHit]) -> dict[str, dict[str, list[str]]]:
    signals: dict[str, dict[str, list[str]]] = {}
    for hit in final_hits:
        buckets: dict[str, list[str]] = {
            "keyword": [],
            "vector": [],
            "graph": [],
            "facet": [],
            "budget": [],
            "soft_preference": [],
            "other": [],
        }
        for reason in hit.reasons:
            if reason.startswith("keyword_match"):
                buckets["keyword"].append(reason)
            elif reason.startswith("vector_hit"):
                buckets["vector"].append(reason)
            elif reason.startswith("graph_"):
                buckets["graph"].append(reason)
            elif reason == "budget_match":
                buckets["budget"].append(reason)
            elif reason.startswith("soft_preference"):
                buckets["soft_preference"].append(reason)
            elif "_match:" in reason:
                buckets["facet"].append(reason)
            else:
                buckets["other"].append(reason)
        signals[hit.product_id] = {key: value for key, value in buckets.items() if value}
    return signals


def _matched_exclude_term(exclude_terms: list[str], item: dict) -> str | None:
    text = product_search_text(item).lower()
    for term in exclude_terms:
        if _has_excluded_risk(text, term.lower()):
            return term
    return None


def _missing_required_effect(intent: QueryIntent, item: dict) -> str | None:
    required_effects = intent.facets.get("effect", [])
    if not required_effects:
        return None
    specific_effects = [
        effect
        for effect in required_effects
        if effect in {"底妆", "定妆", "洁面", "卸妆", "眼周护理", "唇妆", "眉妆"}
    ]
    if specific_effects:
        if any(_matches_specific_effect(effect, item) for effect in specific_effects):
            return None
        return ",".join(specific_effects)
    text = product_search_text(item).lower()
    if any(effect.lower() in text for effect in required_effects):
        return None
    return ",".join(required_effects)


def _matches_specific_effect(effect: str, item: dict) -> bool:
    raw = item["raw"]
    sub_category = str(raw.get("sub_category", ""))
    attrs = item.get("attributes", {})
    tags = {str(tag) for tag in attrs.get("tags", [])}
    allowed_sub_categories = {
        "底妆": {"粉底液"},
        "定妆": {"蜜粉"},
        "洁面": {"洁面"},
        "卸妆": {"卸妆"},
        "眼周护理": {"眼霜"},
        "唇妆": {"唇釉"},
        "眉妆": {"眉笔"},
    }
    return sub_category in allowed_sub_categories.get(effect, set()) or effect in tags


def _has_excluded_risk(text: str, term: str) -> bool:
    if term not in text:
        return False
    if term == "酒精":
        return _has_risky_occurrence(
            text,
            term,
            safe_patterns=[
                r"(不含|无|没有|不添加)[^。；，,.]{0,8}酒精",
                r"酒精[^。；，,.]{0,8}(不含|无|没有|不添加)",
                r"(不含|无|没有|不添加)[^。；，,.]{0,16}酒精[^。；，,.]{0,16}刺激",
            ],
            risk_patterns=[
                r"(含有|包含|添加|如|对|酒精味)[^。；，,.]{0,12}酒精",
                r"酒精[^。；，,.]{0,12}(敏感|味|刺激|含量)",
            ],
        )
    if term == "香精":
        return _has_risky_occurrence(
            text,
            term,
            safe_patterns=[
                r"(不含|无|没有|不添加)[^。；，,.]{0,8}香精",
                r"香精[^。；，,.]{0,8}(不含|无|没有|不添加)",
                r"(不含|无|没有|不添加)[^。；，,.]{0,16}香精[^。；，,.]{0,16}酒精",
            ],
            risk_patterns=[
                r"(含有|包含|添加|如|对|香精味|香味)[^。；，,.]{0,12}香精",
                r"香精[^。；，,.]{0,12}(敏感|味|刺激|含量)",
            ],
        )
    if term == "刺激":
        return _has_risky_occurrence(
            text,
            term,
            safe_patterns=[
                r"(不含|无|没有|不添加)[^。；，,.]{0,12}刺激",
                r"刺激[^。；，,.]{0,8}(不含|无|没有|不添加)",
                r"(舒缓|缓解|改善|减少|降低)[^。；，,.]{0,12}刺激",
                r"刺激[^。；，,.]{0,12}(舒缓|缓解|改善|减少|降低)",
                r"刺激性产品",
            ],
            risk_patterns=[
                r"(可能|容易|会|强烈|明显|产生|造成|导致|带来)[^。；，,.]{0,12}刺激",
                r"刺激[^。；，,.]{0,12}(较强|明显|敏感|刺痛)",
                r"刺激感",
            ],
        )
    return term in text


def _has_risky_occurrence(
    text: str,
    term: str,
    safe_patterns: list[str],
    risk_patterns: list[str],
) -> bool:
    safe_spans = [match.span() for pattern in safe_patterns for match in re.finditer(pattern, text)]
    for pattern in risk_patterns:
        for risk_match in re.finditer(pattern, text):
            term_match = re.search(re.escape(term), risk_match.group(0))
            if term_match is None:
                return True
            term_start = risk_match.start() + term_match.start()
            term_end = risk_match.start() + term_match.end()
            if not any(safe_start <= term_start and term_end <= safe_end for safe_start, safe_end in safe_spans):
                return True
    for match in re.finditer(re.escape(term), text):
        start, end = match.span()
        if not any(safe_start <= start and end <= safe_end for safe_start, safe_end in safe_spans):
            return False
    return False


def _facet_score(intent: QueryIntent, item: dict) -> tuple[float, list[str]]:
    text = product_search_text(item).lower()
    score = 0.0
    reasons: list[str] = []
    weights = {"sub_category": 5.0, "skin_type": 4.0, "effect": 3.0, "use_case": 2.0}
    for facet_name, values in intent.facets.items():
        weight = weights.get(facet_name, 1.0)
        for value in values:
            if value.lower() in text:
                score += weight
                reasons.append(f"{facet_name}_match:{value}")
    for preference in intent.soft_preferences:
        if preference.lower() in text:
            score += 1.0
            reasons.append(f"soft_preference:{preference}")
    return score, reasons


def _graph_score(intent: QueryIntent, item: dict) -> tuple[float, list[str]]:
    raw = item["raw"]
    text = product_search_text(item).lower()
    score = 0.0
    reasons: list[str] = []

    canonical_category = str(
        item.get("canonical_category")
        or CATEGORY_TO_CANONICAL.get(str(raw.get("category", "")), "unknown")
    )
    if intent.category_candidates and canonical_category in intent.category_candidates:
        score += 0.4
        reasons.append(f"graph_category:{canonical_category}")

    for sub_category in intent.facets.get("sub_category", []):
        if str(raw.get("sub_category", "")) == sub_category:
            score += 0.8
            reasons.append(f"graph_sub_category:{sub_category}")

    budget = intent.universal_constraints.budget_max
    if budget is not None and float(raw.get("base_price", 0)) <= budget:
        score += 0.3
        reasons.append("graph_price_within_budget")

    facet_weights = {
        "skin_type": 0.5,
        "effect": 0.5,
        "use_case": 0.4,
    }
    for facet_name, weight in facet_weights.items():
        for value in intent.facets.get(facet_name, []):
            if value.lower() in text:
                score += weight
                reasons.append(f"graph_{facet_name}:{value}")

    for preference in intent.soft_preferences:
        if preference.lower() in text:
            score += 0.2
            reasons.append(f"graph_soft_preference:{preference}")

    return score, reasons


def _is_hard_filtered(item: dict, filtered: list[FilteredProduct]) -> bool:
    product_id = item["raw"]["product_id"]
    return any(entry.product_id == product_id for entry in filtered)


def _matches_category_candidate(raw_category: str, candidates: list[str]) -> bool:
    allowed = {CATEGORY_TO_RAW[candidate] for candidate in candidates if candidate in CATEGORY_TO_RAW}
    return not allowed or raw_category in allowed


def _no_result_clarification(intent: QueryIntent) -> str:
    constraints: list[str] = []
    budget = intent.universal_constraints.budget_max
    if budget is not None:
        constraints.append(f"{budget:g}元以内")
    skin_types = intent.facets.get("skin_type", [])
    if skin_types:
        constraints.append(f"肤质：{'、'.join(skin_types)}")
    effects = intent.facets.get("effect", [])
    if effects:
        constraints.append(f"功效：{'、'.join(effects)}")
    use_cases = intent.facets.get("use_case", [])
    if use_cases:
        constraints.append(f"场景：{'、'.join(use_cases)}")
    if intent.exclude_terms:
        constraints.append(f"避开：{'、'.join(intent.exclude_terms)}")

    if constraints:
        joined = "；".join(constraints)
        return (
            f"当前商品池里没有同时满足「{joined}」的商品。"
            "你想优先放宽哪一项：预算、排除条件，还是先只看其中一个功效/场景？"
        )
    return "当前商品池里没有足够匹配的商品。你想优先补充预算、肤质，还是主要功效？"


def _vector_scores(
    query: str,
    index_dir: Path | None,
    intent: QueryIntent,
) -> tuple[dict[str, float], list[RetrievalHit], dict]:
    where = _metadata_where(intent)
    if index_dir is None or not index_dir.exists():
        return {}, [], where or {}
    try:
        import chromadb
        from chromadb.config import Settings

        model = sentence_model()
        embedding = model.encode([query], normalize_embeddings=True)[0].tolist()
        with contextlib.redirect_stderr(io.StringIO()):
            client = chromadb.PersistentClient(
                path=str(index_dir),
                settings=Settings(anonymized_telemetry=False),
            )
            collection = _get_products_collection(client)
            collection_size = collection.count()
            if collection_size == 0:
                return {}, [], where or {}
            query_kwargs = {
                "query_embeddings": [embedding],
                "n_results": min(8, collection_size),
            }
            if where is not None:
                query_kwargs["where"] = where
            result = collection.query(**query_kwargs)
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0] if result.get("distances") else []
        scores: dict[str, float] = {}
        hits: list[RetrievalHit] = []
        filter_reason = f"metadata_filter:{where}" if where is not None else "metadata_filter:none"
        for rank, product_id in enumerate(ids):
            distance = float(distances[rank]) if rank < len(distances) else float(rank)
            score = max(0.0, 8.0 - rank) + max(0.0, 1.0 - distance)
            scores[product_id] = score
            hits.append(
                RetrievalHit(
                    product_id=product_id,
                    score=round(score, 3),
                    reasons=[f"vector_rank:{rank}", filter_reason],
                )
            )
        return scores, hits, where or {}
    except Exception:
        return {}, [], where or {}


def _get_products_collection(client):
    try:
        return client.get_collection("products")
    except Exception:
        return client.get_collection("beauty_products")


def _metadata_where(intent: QueryIntent) -> dict | None:
    clauses: list[dict] = []
    category_candidates = intent.category_candidates
    if category_candidates:
        clauses.append(_field_filter("canonical_category", category_candidates))

    sub_categories = intent.facets.get("sub_category", [])
    if sub_categories:
        clauses.append(_field_filter("sub_category", sub_categories))

    budget = intent.universal_constraints.budget_max
    if budget is not None:
        clauses.append({"base_price": {"$lte": budget}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _field_filter(field: str, values: list[str]) -> dict:
    unique_values = list(dict.fromkeys(values))
    if len(unique_values) == 1:
        return {field: unique_values[0]}
    return {field: {"$in": unique_values}}


def _to_card(item: dict, query: str) -> ProductCard:
    raw = item["raw"]
    attrs = item.get("attributes", {})
    display = item.get("display", {})
    knowledge = raw.get("rag_knowledge", {})
    tags = list(dict.fromkeys(attrs.get("tags", [])[:5]))
    reason = (
        item.get("card_reason")
        or display.get("card_reason")
        or "匹配本次需求，推荐理由来自商品资料和结构化标签。"
    )
    if "防晒" in query and raw["sub_category"] == "防晒":
        reason = "防晒相关需求匹配；请结合肤质、户外时长和补涂频率选择。"
    return ProductCard(
        product_id=raw["product_id"],
        title=raw["title"],
        brand=raw["brand"],
        category=raw["category"],
        sub_category=raw["sub_category"],
        price=float(raw["base_price"]),
        image_path=raw["image_path"],
        tags=tags,
        reason=reason,
        target_users=_string_list(attrs.get("target_users", [])),
        use_cases=_string_list(attrs.get("use_cases", [])),
        selling_points=_string_list(attrs.get("selling_points", [])),
        cautions=_string_list(attrs.get("cautions", [])),
        suitable_for=_string_list(attrs.get("suitable_for", [])),
        avoid_for=_string_list(attrs.get("avoid_for", [])),
        description=_knowledge_text(knowledge),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _knowledge_text(knowledge: dict) -> str:
    parts: list[str] = []
    marketing_description = knowledge.get("marketing_description", "")
    if marketing_description:
        parts.append(str(marketing_description))
    for item in knowledge.get("official_faq", []):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if question or answer:
            parts.append(f"官方FAQ：{question} {answer}".strip())
    for item in knowledge.get("user_reviews", []):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if content:
            parts.append(f"用户评价：{content}")
    return "\n".join(parts)


def _context_block(item: dict) -> str:
    raw = item["raw"]
    knowledge = raw.get("rag_knowledge", {})
    attrs = item.get("attributes", {})
    beauty = item.get("beauty_attributes", {})
    category_attrs = item.get("category_attributes", {})
    variants = item.get("variants", {})
    source = item.get("source", {})
    return f"""商品ID: {raw['product_id']}
标题: {raw['title']}
品牌: {raw['brand']}
类目: {raw['category']} / {raw['sub_category']}
价格: {raw['base_price']}
结构化标签: {attrs}
美妆属性: {beauty}
品类属性: {category_attrs}
变体维度: {variants}
证据来源: {source}
商品资料: {_knowledge_text(knowledge)}
"""
