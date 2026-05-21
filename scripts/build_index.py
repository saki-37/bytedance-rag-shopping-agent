#!/usr/bin/env python3
"""Build a local Chroma index for enriched beauty products."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENRICHED_PATH = ROOT / "data" / "enriched" / "beauty_products.jsonl"
INDEX_DIR = ROOT / "data" / "indexes" / "chroma"


def main() -> None:
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit(
            "Missing RAG dependencies. Run: cd server && pip install -r requirements.txt"
        ) from exc

    rows = [
        json.loads(line)
        for line in ENRICHED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    collection = client.get_or_create_collection("beauty_products")
    ids = [row["raw_product_id"] for row in rows]
    documents = [json.dumps(row, ensure_ascii=False) for row in rows]
    embeddings = model.encode(documents, normalize_embeddings=True).tolist()
    collection.upsert(ids=ids, documents=documents, embeddings=embeddings)
    print(f"Indexed {len(rows)} beauty products into {INDEX_DIR}")


if __name__ == "__main__":
    main()
