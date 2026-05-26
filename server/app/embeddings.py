from functools import lru_cache
from pathlib import Path


SENTENCE_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def resolve_sentence_model_path(model_id: str = SENTENCE_MODEL_ID) -> str:
    """Use a local HuggingFace snapshot when it exists to avoid slow online HEAD checks."""
    cache_name = f"models--{model_id.replace('/', '--')}"
    cache_root = Path.home() / ".cache" / "huggingface" / "hub" / cache_name
    refs_main = cache_root / "refs" / "main"
    if refs_main.exists():
        snapshot = cache_root / "snapshots" / refs_main.read_text(encoding="utf-8").strip()
        if _looks_like_sentence_transformer_snapshot(snapshot):
            return str(snapshot)

    snapshots_dir = cache_root / "snapshots"
    if snapshots_dir.exists():
        snapshots = sorted(
            (path for path in snapshots_dir.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for snapshot in snapshots:
            if _looks_like_sentence_transformer_snapshot(snapshot):
                return str(snapshot)

    return model_id


@lru_cache(maxsize=1)
def sentence_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(resolve_sentence_model_path())


def _looks_like_sentence_transformer_snapshot(path: Path) -> bool:
    return (
        path.exists()
        and (path / "config.json").exists()
        and (path / "modules.json").exists()
        and (path / "1_Pooling" / "config.json").exists()
    )
