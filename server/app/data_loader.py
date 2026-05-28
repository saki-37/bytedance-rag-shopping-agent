import json
from pathlib import Path
from typing import Any

CATEGORY_TO_CANONICAL = {
    "美妆护肤": "beauty",
    "服饰运动": "apparel",
    "数码电子": "digital",
    "食品饮料": "food",
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_raw_products(raw_root: Path) -> dict[str, dict[str, Any]]:
    products: dict[str, dict[str, Any]] = {}
    for path in sorted(raw_root.glob("*/data/*.json")):
        item = read_json(path)
        item["_raw_path"] = str(path)
        products[item["product_id"]] = item
    return products


def load_enriched_products(path: Path, raw_products: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    paths = sorted(path.glob("*_products.jsonl")) if path.is_dir() else [path]
    enriched: list[dict[str, Any]] = []
    for enriched_path in paths:
        with enriched_path.open(encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                raw_id = item["raw_product_id"]
                if raw_id not in raw_products:
                    raise ValueError(f"Missing raw product for enriched item: {raw_id}")
                item["_enriched_path"] = str(enriched_path)
                item["_enriched_line"] = line_number
                item["raw"] = raw_products[raw_id]
                enriched.append(item)
    return enriched


def product_search_text(item: dict[str, Any]) -> str:
    raw = item["raw"]
    attrs = item.get("attributes", {})
    beauty = item.get("beauty_attributes", {})
    category_attrs = item.get("category_attributes", {})
    display = item.get("display", {})
    variants = item.get("variants", {})
    retrieval = item.get("retrieval", {})
    knowledge = raw.get("rag_knowledge", {})
    faq_text = " ".join(
        f"{faq.get('question', '')} {faq.get('answer', '')}"
        for faq in knowledge.get("official_faq", [])
    )
    review_text = " ".join(
        review.get("content", "")
        for review in knowledge.get("user_reviews", [])
    )
    structured = " ".join(
        str(value)
        for value in [
            attrs.get("target_users", []),
            attrs.get("use_cases", []),
            attrs.get("selling_points", []),
            attrs.get("cautions", []),
            attrs.get("avoid_for", []),
            attrs.get("suitable_for", []),
            attrs.get("tags", []),
            attrs.get("decision_factors", []),
            attrs.get("quality_risks", []),
            attrs.get("care_or_usage_notes", []),
            attrs.get("specifications", []),
            beauty,
            category_attrs,
            display,
            variants,
            retrieval,
        ]
    )
    return " ".join(
        [
            raw.get("title", ""),
            raw.get("brand", ""),
            raw.get("category", ""),
            raw.get("sub_category", ""),
            knowledge.get("marketing_description", ""),
            faq_text,
            review_text,
            structured,
        ]
    )


def product_index_metadata(item: dict[str, Any]) -> dict[str, str | float | int | bool]:
    raw = item["raw"]
    raw_category = str(raw.get("category", ""))
    canonical_category = item.get("canonical_category") or CATEGORY_TO_CANONICAL.get(raw_category, "unknown")
    return {
        "raw_product_id": str(raw.get("product_id", "")),
        "canonical_category": str(canonical_category),
        "raw_category": raw_category,
        "sub_category": str(raw.get("sub_category", "")),
        "base_price": float(raw.get("base_price", 0)),
        "schema_version": str(item.get("schema_version", "1.0")),
        "enriched_source": str(Path(item.get("_enriched_path", "")).name),
    }
