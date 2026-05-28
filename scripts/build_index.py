#!/usr/bin/env python3
"""Build a local Chroma index for all enriched products."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.data_loader import (
    load_enriched_products,
    load_raw_products,
    product_index_metadata,
    product_search_text,
)
from app.embeddings import resolve_sentence_model_path

RAW_ROOT = ROOT / "data" / "raw" / "ecommerce_agent_dataset"
ENRICHED_DIR = ROOT / "data" / "enriched"
INDEX_DIR = ROOT / "data" / "indexes" / "chroma"
COLLECTION_NAME = "products"


def main() -> None:
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit(
            "Missing RAG dependencies. Run: cd server && pip install -r requirements.txt"
        ) from exc

    raw_products = load_raw_products(RAW_ROOT)
    rows = load_enriched_products(ENRICHED_DIR, raw_products)
    if not rows:
        raise SystemExit(f"No enriched products found in {ENRICHED_DIR}")

    model_path = resolve_sentence_model_path()
    model = SentenceTransformer(model_path)
    ids = [row["raw_product_id"] for row in rows]
    documents = [product_search_text(row) for row in rows]
    metadatas = [product_index_metadata(row) for row in rows]
    embeddings = model.encode(documents, normalize_embeddings=True).tolist()
    with contextlib.redirect_stderr(io.StringIO()):
        client = chromadb.PersistentClient(
            path=str(INDEX_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        with contextlib.suppress(Exception):
            client.delete_collection(COLLECTION_NAME)
        collection = client.get_or_create_collection(COLLECTION_NAME)
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    category_counts: dict[str, int] = {}
    for metadata in metadatas:
        category = str(metadata["canonical_category"])
        category_counts[category] = category_counts.get(category, 0) + 1
    print(f"Indexed {len(rows)} products into {INDEX_DIR}/{COLLECTION_NAME}: {category_counts}")


if __name__ == "__main__":
    main()
