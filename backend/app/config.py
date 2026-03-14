from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/ardenta.db"
    upload_dir: str = "../images"

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    vision_model: str = "google/gemini-2.0-flash-001"
    llm_model: str = "google/gemini-2.0-flash-001"
    embedding_model: str = "openai/text-embedding-3-small"

    # API auth
    api_key: str = ""  # Set to require X-API-Key header; empty = no auth

    # Caching
    embedding_cache_size: int = 256
    llm_cache_size: int = 64

    # Processing
    analysis_concurrency: int = 4  # Max parallel vision API calls

    model_config = {"env_file": [
        ".env", ".env.local"], "env_file_encoding": "utf-8"}


settings = Settings()


def ensure_dirs() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path("./data").mkdir(parents=True, exist_ok=True)
