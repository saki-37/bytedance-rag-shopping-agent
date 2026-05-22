import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.data_loader import product_search_text
from app.models import ProductCard


@dataclass
class RetrievalResult:
    cards: list[ProductCard]
    context: str


def _query_terms(query: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{1,4}", query):
        token = token.strip().lower()
        if token:
            terms.add(token)
    return terms


def _max_budget(query: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*元?以[内下]", query)
    if match:
        return float(match.group(1))
    match = re.search(r"预算\s*(\d+(?:\.\d+)?)", query)
    if match:
        return float(match.group(1))
    return None


def _structured_bonus(query: str, item: dict) -> int:
    text = product_search_text(item)
    bonus = 0
    intent_pairs = [
        ("油皮", ["油皮", "混油", "控油", "清爽"]),
        ("敏感", ["敏感肌", "舒缓", "修护", "屏障", "温和"]),
        ("干皮", ["干皮", "保湿", "滋润", "补水"]),
        ("防晒", ["防晒", "spf", "pa", "通勤", "户外"]),
        ("抗初老", ["抗初老", "淡纹", "紧致", "抗皱"]),
        ("提亮", ["提亮", "亮肤", "美白", "暗沉"]),
        ("底妆", ["粉底", "蜜粉", "定妆", "持妆"]),
        ("控油", ["控油", "清爽", "油皮", "定妆"]),
    ]
    for trigger, needles in intent_pairs:
        if trigger in query:
            bonus += sum(3 for needle in needles if needle.lower() in text.lower())
    return bonus


def retrieve(query: str, products: list[dict], limit: int = 3, index_dir: Path | None = None) -> RetrievalResult:
    budget = _max_budget(query)
    terms = _query_terms(query)
    vector_rank = _vector_rank(query, index_dir)
    scored: list[tuple[int, dict]] = []

    for item in products:
        raw = item["raw"]
        if budget is not None and float(raw["base_price"]) > budget:
            continue
        text = product_search_text(item).lower()
        score = sum(1 for term in terms if term.lower() in text)
        score += _structured_bonus(query, item)
        if raw["product_id"] in vector_rank:
            score += max(0, 20 - vector_rank[raw["product_id"]])
        if score > 0:
            scored.append((score, item))

    if not scored:
        scored = [(0, item) for item in products if budget is None or float(item["raw"]["base_price"]) <= budget]

    scored.sort(key=lambda pair: (pair[0], -float(pair[1]["raw"]["base_price"])), reverse=True)
    selected = [item for _, item in scored[:limit]]

    cards = [_to_card(item, query) for item in selected]
    context = "\n\n".join(_context_block(item) for item in selected)
    return RetrievalResult(cards=cards, context=context)


def _vector_rank(query: str, index_dir: Path | None) -> dict[str, int]:
    if index_dir is None or not index_dir.exists():
        return {}
    try:
        import chromadb

        model = _sentence_model()
        embedding = model.encode([query], normalize_embeddings=True)[0].tolist()
        client = chromadb.PersistentClient(path=str(index_dir))
        collection = client.get_collection("beauty_products")
        result = collection.query(query_embeddings=[embedding], n_results=8)
        ids = result.get("ids", [[]])[0]
        return {product_id: rank for rank, product_id in enumerate(ids)}
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _sentence_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


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
