#!/usr/bin/env python3
"""Validate raw and enriched product data for the MVP."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "ecommerce_agent_dataset"
ENRICHED_PATH = ROOT / "data" / "enriched" / "beauty_products.jsonl"

REQUIRED_RAW_FIELDS = {
    "product_id",
    "title",
    "brand",
    "category",
    "sub_category",
    "base_price",
    "image_path",
    "skus",
    "rag_knowledge",
}


def main() -> None:
    products = load_raw_products()
    validate_raw(products)
    if ENRICHED_PATH.exists():
        validate_enriched(products)
    print(f"OK raw_products={len(products)} enriched_exists={ENRICHED_PATH.exists()}")


def load_raw_products() -> dict[str, dict]:
    if not RAW_ROOT.exists():
        raise SystemExit(f"Missing raw dataset: {RAW_ROOT}")

    products: dict[str, dict] = {}
    for path in sorted(RAW_ROOT.glob("*/data/*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        item["_path"] = path
        product_id = item.get("product_id")
        if not product_id:
            raise AssertionError(f"Missing product_id in {path}")
        if product_id in products:
            raise AssertionError(f"Duplicated product_id: {product_id}")
        products[product_id] = item
    return products


def validate_raw(products: dict[str, dict]) -> None:
    if len(products) != 100:
        raise AssertionError(f"Expected 100 raw products, got {len(products)}")

    image_count = 0
    for product_id, item in products.items():
        missing = REQUIRED_RAW_FIELDS - set(item)
        if missing:
            raise AssertionError(f"{product_id} missing fields: {sorted(missing)}")
        knowledge = item["rag_knowledge"]
        for key in ["marketing_description", "official_faq", "user_reviews"]:
            if key not in knowledge or not knowledge[key]:
                raise AssertionError(f"{product_id} missing rag_knowledge.{key}")
        image_path = RAW_ROOT / item["image_path"]
        if not image_path.exists():
            raise AssertionError(f"{product_id} image not found: {image_path}")
        image_count += 1

    if image_count != 100:
        raise AssertionError(f"Expected 100 images referenced, got {image_count}")


def validate_enriched(products: dict[str, dict]) -> None:
    rows = []
    for line_number, line in enumerate(ENRICHED_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        raw_id = row.get("raw_product_id")
        if raw_id not in products:
            raise AssertionError(f"Line {line_number}: raw_product_id not found: {raw_id}")
        for field in ["attributes", "beauty_attributes", "card_reason"]:
            if field not in row:
                raise AssertionError(f"Line {line_number}: missing {field}")
        rows.append(row)

    if len(rows) < 5:
        raise AssertionError(f"Expected at least 5 enriched beauty rows, got {len(rows)}")


if __name__ == "__main__":
    main()
