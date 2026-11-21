"""Runtime settings, read from environment variables."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'srk_placement.db'}")
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    # Unset -> a random secret per process (logins reset on restart). Always set it in production.
    jwt_secret: str = os.getenv("JWT_SECRET") or secrets.token_hex(32)
    jwt_expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "480"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "5"))
    cors_origins: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    # Optional LLM / embedding providers. "none" keeps everything local and free.
    llm_provider: str = os.getenv("LLM_PROVIDER", "none")
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "tfidf")
    consent_version: str = os.getenv("CONSENT_VERSION", "2026-11-v1")


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
