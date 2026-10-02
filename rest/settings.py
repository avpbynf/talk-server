"""Application settings module."""

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WHISPER_MODEL: str = "Systran/faster-whisper-large-v3"
    DEVICE: str = "cuda"
    COMPUTE_TYPE: str = "int8_float16"
    GPU_TIMEOUT: int = 120
    GPU_CONCURRENCY: int = 1
    CORS_ALLOW_ORIGINS: list[str] = ["*"]
    LOG_LEVEL: str = "INFO"
    DEFAULT_LANGUAGE: str = "fr"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/tokens.db"
    ADMIN_TOKEN: str = ""
    MDNS_ENABLED: bool = True
    PAIRING_ENABLED: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def pairing_active(self) -> bool:
        """Pairing mints tokens, so it needs an admin to exist."""
        return self.PAIRING_ENABLED and bool(self.ADMIN_TOKEN)


@functools.lru_cache
def get_settings() -> Settings:
    """Return the settings singleton.

    Returns:
        Settings: Cached application settings instance.
    """
    return Settings()
