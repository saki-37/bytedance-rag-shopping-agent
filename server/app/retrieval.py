import contextlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

from app.data_loader import product_search_text
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
        "抗初老": ["抗初老", "抗老", "淡纹", "紧致", "抗皱"],
        "底妆": ["底妆", "粉底", "粉底液", "遮瑕"],
        "定妆": ["定妆", "蜜粉", "散粉", "持妆"],
    },
    "use_case": {
        "通勤": ["通勤", "上班", "日常"],
        "户外": ["户外", "海边", "爬山", "旅行", "三亚"],
        "运动": ["运动", "跑步", "健身", "防汗"],
        "妆前": ["妆前", "打底", "上妆"],
        "夜间": ["夜间", "晚上", "睡前"],
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
    "洗面奶",
    "定妆",
]

GENERIC_RECOMMEND_TERMS = ["推荐", "买什么", "护肤品", "化妆品", "随便", "看看"]
EXCLUDE_TERMS = ["酒精", "刺激", "刺痛", "太油", "油腻", "厚重", "拔干", "日系"]
SOFT_PREFERENCE_TERMS = ["便宜", "清爽", "轻薄", "温和", "自然", "滋润", "高倍", "防水", "防汗"]


def _query_terms(query: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{1,4}", query):
        token = token.strip().lower()
        if token:
            terms.add(token)
    return terms


def parse_query_intent(query: str) -> QueryIntent:
    budget = _hard_budget(query)
    facets = _extract_facets(query)
    exclude_terms = _extract_exclude_terms(query)
    soft_preferences = _extract_soft_preferences(query)
    category_candidates = ["beauty"] if _looks_like_beauty_query(query, facets) or exclude_terms else []
    hard_constraints: list[str] = []
    if budget is not None:
        hard_constraints.append(f"budget_max <= {budget:g}")
    hard_constraints.extend(f"exclude:{term}" for term in exclude_terms)

    signal_count = (
        len(exclude_terms)
        + len(soft_preferences)
        + sum(len(values) for values in facets.values())
        + (1 if budget is not None else 0)
    )
    needs_clarification = _needs_clarification(query, signal_count)
    confidence = min(0.95, 0.2 + signal_count * 0.15 + (0.1 if category_candidates else 0.0))
    return QueryIntent(
        category_candidates=category_candidates,
        universal_constraints=UniversalConstraints(budget_max=budget),
        facets=facets,
        hard_constraints=hard_constraints,
        soft_preferences=soft_preferences,
        exclude_terms=exclude_terms,
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
        r"(?:预算|价格|价位)\s*(?:在|不超过|别超过|低于|小于|不高于|<=)?\s*(\d+(?:\.\d+)?)",
        r"(?:不超过|别超过|低于|小于|不高于|<=)\s*(\d+(?:\.\d+)?)\s*元?",
    ]
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return float(match.group(1))
    return None


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
        if term in query and re.search(rf"(不要|不想|不含|避开|排除|别太|不能).*{re.escape(term)}", query):
            terms.append(term)
    return list(dict.fromkeys(terms))


def _extract_soft_preferences(query: str) -> list[str]:
    return [term for term in SOFT_PREFERENCE_TERMS if term in query]


def _looks_like_beauty_query(query: str, facets: dict[str, list[str]]) -> bool:
    if any(term in query for term in BEAUTY_TERMS):
        return True
    return any(key in facets for key in ["skin_type", "effect"])


def _needs_clarification(query: str, signal_count: int) -> bool:
    if signal_count > 0:
        return False
    return any(term in query for term in GENERIC_RECOMMEND_TERMS)


def retrieve(query: str, products: list[dict], limit: int = 3, index_dir: Path | None = None) -> RetrievalResult:
    intent = parse_query_intent(query)
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
    vector_scores, vector_hits = _vector_scores(query, index_dir)
    keyword_hits: list[RetrievalHit] = []
    final_hits: list[RetrievalHit] = []
    hard_filtered_out: list[FilteredProduct] = []
    scored: list[tuple[float, dict, list[str]]] = []

    for item in products:
        raw = item["raw"]
        if budget is not None and float(raw["base_price"]) > budget:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"price {raw['base_price']} > budget {budget:g}")
            )
            continue
        excluded_term = _matched_exclude_term(intent.exclude_terms, item)
        if excluded_term is not None:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"matches excluded term: {excluded_term}")
            )
            continue
        text = product_search_text(item).lower()
        score = 0.0
        reasons: list[str] = []
        keyword_score = sum(1 for term in terms if len(term) >= 2 and term.lower() in text)
        if keyword_score:
            score += keyword_score
            reasons.append(f"keyword_match:{keyword_score:g}")
            keyword_hits.append(RetrievalHit(product_id=raw["product_id"], score=float(keyword_score), reasons=["keyword_match"]))
        facet_score, facet_reasons = _facet_score(intent, item)
        score += facet_score
        reasons.extend(facet_reasons)
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
        hard_filtered_out=hard_filtered_out,
        retrieval_channels=RetrievalChannels(
            keyword=sorted(keyword_hits, key=lambda hit: hit.score, reverse=True)[:8],
            vector=vector_hits,
            graph=[],
        ),
        final_ranking=final_hits,
        guardrail_checks=GuardrailChecks(
            over_budget_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("price")),
            excluded_term_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("matches excluded")),
            needs_clarification=False,
        ),
    )
    return RetrievalResult(cards=cards, context=context, trace=trace)


def _matched_exclude_term(exclude_terms: list[str], item: dict) -> str | None:
    text = product_search_text(item).lower()
    for term in exclude_terms:
        if term.lower() in text:
            return term
    return None


def _facet_score(intent: QueryIntent, item: dict) -> tuple[float, list[str]]:
    text = product_search_text(item).lower()
    score = 0.0
    reasons: list[str] = []
    weights = {"skin_type": 4.0, "effect": 3.0, "use_case": 2.0}
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


def _is_hard_filtered(item: dict, filtered: list[FilteredProduct]) -> bool:
    product_id = item["raw"]["product_id"]
    return any(entry.product_id == product_id for entry in filtered)


def _vector_scores(query: str, index_dir: Path | None) -> tuple[dict[str, float], list[RetrievalHit]]:
    if index_dir is None or not index_dir.exists():
        return {}, []
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
            collection = client.get_collection("beauty_products")
            collection_size = collection.count()
            if collection_size == 0:
                return {}, []
            result = collection.query(query_embeddings=[embedding], n_results=min(8, collection_size))
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0] if result.get("distances") else []
        scores: dict[str, float] = {}
        hits: list[RetrievalHit] = []
        for rank, product_id in enumerate(ids):
            distance = float(distances[rank]) if rank < len(distances) else float(rank)
            score = max(0.0, 8.0 - rank) + max(0.0, 1.0 - distance)
            scores[product_id] = score
            hits.append(RetrievalHit(product_id=product_id, score=round(score, 3), reasons=[f"vector_rank:{rank}"]))
        return scores, hits
    except Exception:
        return {}, []


def _to_card(item: dict, query: str) -> ProductCard:
    raw = item["raw"]
    attrs = item.get("attributes", {})
    knowledge = raw.get("rag_knowledge", {})
    tags = list(dict.fromkeys(attrs.get("tags", [])[:5]))
    reason = item.get("card_reason") or "匹配本次需求，推荐理由来自商品资料和结构化标签。"
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
        description=knowledge.get("marketing_description", ""),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _context_block(item: dict) -> str:
    raw = item["raw"]
    knowledge = raw.get("rag_knowledge", {})
    attrs = item.get("attributes", {})
    beauty = item.get("beauty_attributes", {})
    return f"""商品ID: {raw['product_id']}
标题: {raw['title']}
品牌: {raw['brand']}
类目: {raw['category']} / {raw['sub_category']}
价格: {raw['base_price']}
结构化标签: {attrs}
美妆属性: {beauty}
商品资料: {knowledge.get('marketing_description', '')}
"""
