"""
Application settings sourced from .env with stable lookup and runtime validation.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Optional[Path]:
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate

    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate

    return None


_ENV_PATH = _find_env_file()
if _ENV_PATH is not None:
    load_dotenv(dotenv_path=_ENV_PATH, override=False)


class DBSettings(BaseModel):
    """Database connection settings."""

    url: str


class Settings(BaseSettings):
    """Unified settings model."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH) if _ENV_PATH is not None else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = Field(
        default="",
        validation_alias=AliasChoices("DB_URL", "DATABASE_URL", "DB__URL"),
    )
    log_level: str = "INFO"

    @property
    def db(self) -> DBSettings:
        if not self.db_url:
            raise RuntimeError("DB_URL is required (set it in .env or environment)")
        return DBSettings(url=self.db_url)


@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
