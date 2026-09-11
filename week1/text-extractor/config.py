"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Text Extractor"

    # Database
    database_url: str = f"sqlite:///{BASE_DIR / 'storage' / 'text_extractor.db'}"

    # Uploads
    upload_dir: Path = BASE_DIR / "storage" / "uploads"
    max_upload_mb: int = 25
    keep_uploaded_files: bool = True

    # Chunking (used to build the context passed to the LLM)
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # Retrieval
    retrieval_top_k: int = 6
    # Candidates pulled per channel BEFORE fusion; must exceed retrieval_top_k.
    retrieval_candidates: int = 30
    # Reciprocal Rank Fusion constant (Cormack et al.); 60 is the standard value.
    rrf_k: int = 60
    # Leading chunks used when retrieval finds nothing, or the question is
    # about the document as a whole ("what is this about?", "summarise it").
    fallback_leading_chunks: int = 3

    # Embeddings (dense half of the hybrid retrieval)
    embedding_enabled: bool = True
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_provider: str = "deepinfra"
    # bge-large is 1024-dim. bge-small/MiniLM are 384 - changing the model
    # means changing this and re-running scripts.backfill_embeddings --force.
    embedding_dim: int = 1024

    # CORS (frontend origins)
    cors_origins: list[str] = ["*"]

    # LLM model tiering
    # Flagship model for answer generation (grounded QA)
    main_model: str = "openai/gpt-oss-120b"
    # Lightweight model for rewrites, summaries and other simple tasks
    fast_model: str = "llama-3.1-8b-instant"
    # Hard session limits
    max_session_turns: int = 30
    max_session_tokens: int = 50_000

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
