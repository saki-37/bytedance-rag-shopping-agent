from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    mock_llm: bool = True
    ark_api_key: str | None = None
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3/"
    ark_model: str | None = None

    raw_data_dir: Path = ROOT_DIR / "data" / "raw" / "ecommerce_agent_dataset"
    enriched_data_dir: Path = ROOT_DIR / "data" / "enriched"
    enriched_beauty_path: Path = ROOT_DIR / "data" / "enriched" / "beauty_products.jsonl"
    index_dir: Path = ROOT_DIR / "data" / "indexes" / "chroma"
    image_base_path: Path = ROOT_DIR / "data" / "raw" / "ecommerce_agent_dataset"
    feedback_dir: Path = ROOT_DIR / "data" / "tmp" / "feedback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
