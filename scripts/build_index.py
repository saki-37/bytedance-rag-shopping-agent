#!/usr/bin/env python3
"""Build a local Chroma index for enriched beauty products."""

from __future__ import annotations

import json
import contextlib
import io
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.embeddings import resolve_sentence_model_path

ENRICHED_PATH = ROOT / "data" / "enriched" / "beauty_products.jsonl"
INDEX_DIR = ROOT / "data" / "indexes" / "chroma"


def main() -> None:
    try:
        import chromadb
        from chromadb.config import Settings
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
    model_path = resolve_sentence_model_path()
    model = SentenceTransformer(model_path)
    ids = [row["raw_product_id"] for row in rows]
    documents = [json.dumps(row, ensure_ascii=False) for row in rows]
    embeddings = model.encode(documents, normalize_embeddings=True).tolist()
    with contextlib.redirect_stderr(io.StringIO()):
        client = chromadb.PersistentClient(
            path=str(INDEX_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        collection = client.get_or_create_collection("beauty_products")
        collection.upsert(ids=ids, documents=documents, embeddings=embeddings)
    print(f"Indexed {len(rows)} beauty products into {INDEX_DIR}")


if __name__ == "__main__":
    main()
