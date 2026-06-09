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
    mock_llm: bool = False
    llm_provider: str = "ark"

    ark_api_key: str | None = None
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3/"
    ark_model: str | None = None

    yunwu_api_key: str | None = None
    yunwu_base_url: str = "https://yunwu.ai/v1"
    yunwu_model: str | None = None

    planner_timeout_seconds: float = 20.0
    fast_first_screen_enabled: bool = True
    fast_quick_reply_deadline_seconds: float = 0.8

    raw_data_dir: Path = ROOT_DIR / "data" / "raw" / "ecommerce_agent_dataset"
    enriched_data_dir: Path = ROOT_DIR / "data" / "enriched"
    enriched_beauty_path: Path = ROOT_DIR / "data" / "enriched" / "beauty_products.jsonl"
    index_dir: Path = ROOT_DIR / "data" / "indexes" / "chroma"
    image_base_path: Path = ROOT_DIR / "data" / "raw" / "ecommerce_agent_dataset"
    feedback_dir: Path = ROOT_DIR / "data" / "tmp" / "feedback"
    trace_dir: Path = ROOT_DIR / "data" / "tmp" / "traces"
    asr_sidecar_url: str = "http://127.0.0.1:8765/transcribe"
    asr_upload_dir: Path = ROOT_DIR / "data" / "tmp" / "asr" / "uploads"
    asr_max_upload_mb: int = 50
    asr_timeout_seconds: float = 180.0

    @property
    def active_llm_provider(self) -> str:
        provider = self.llm_provider.strip().lower()
        if provider in {"ark", "doubao", "volcengine"}:
            return "ark"
        if provider in {"yunwu", "demo"}:
            return "yunwu"
        return provider

    @property
    def llm_api_key(self) -> str | None:
        if self.active_llm_provider == "yunwu":
            return self.yunwu_api_key
        if self.active_llm_provider == "ark":
            return self.ark_api_key
        return None

    @property
    def llm_base_url(self) -> str:
        if self.active_llm_provider == "yunwu":
            return self.yunwu_base_url
        return self.ark_base_url

    @property
    def llm_model(self) -> str | None:
        if self.active_llm_provider == "yunwu":
            return self.yunwu_model
        if self.active_llm_provider == "ark":
            return self.ark_model
        return None

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
