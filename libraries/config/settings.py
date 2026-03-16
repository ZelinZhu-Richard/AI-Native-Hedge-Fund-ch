from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    project_name: str = Field(
        default="ANHF Research OS",
        validation_alias="PROJECT_NAME",
        description="Human-readable project name.",
    )
    environment: str = Field(
        default="local",
        validation_alias="ENVIRONMENT",
        description="Current runtime environment name.",
    )
    api_host: str = Field(
        default="127.0.0.1",
        validation_alias="API_HOST",
        description="Default bind host for local API runs.",
    )
    api_port: int = Field(
        default=8000,
        validation_alias="API_PORT",
        description="Default bind port for local API runs.",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Application log level.",
    )
    default_timezone: str = Field(
        default="UTC",
        validation_alias="DEFAULT_TIMEZONE",
        description="Timezone used for validation and developer defaults.",
    )
    artifact_root: Path = Field(
        default=Path("artifacts"),
        validation_alias="ARTIFACT_ROOT",
        description="Base directory for local artifacts and future persisted outputs.",
    )
    enable_paper_trading: bool = Field(
        default=False,
        validation_alias="ENABLE_PAPER_TRADING",
        description="Feature flag for simulated execution workflows.",
    )
    allow_live_trading: bool = Field(
        default=False,
        validation_alias="ALLOW_LIVE_TRADING",
        description="Must remain false on Day 1.",
    )
    model_registry_version: str = Field(
        default="day1",
        validation_alias="MODEL_REGISTRY_VERSION",
        description="Registry version for prompt/model configs.",
    )
    app_version: str = Field(default="0.1.0", description="Application version string.")

    @property
    def resolved_artifact_root(self) -> Path:
        """Return the artifact root as an absolute path."""

        if self.artifact_root.is_absolute():
            return self.artifact_root
        return Path.cwd() / self.artifact_root


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache runtime settings."""

    return Settings()
