"""Application settings.

Everything is overridable through environment variables (or a `.env` file at
the repository root) using the `FITDASH_` prefix, e.g. `FITDASH_LOOKBACK_DAYS=365`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FITDASH_",
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Paths -----------------------------------------------------------
    data_dir: Path = REPO_ROOT / "data"
    db_path: Path | None = None
    token_dir: Path = REPO_ROOT / ".garmin_tokens"
    fit_cache_dir: Path | None = None  # set to keep raw .fit files on disk
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"

    # --- Garmin / sync -----------------------------------------------------
    garmin_is_cn: bool = False
    lookback_days: int = 90  # initial backfill window (user adjustable in UI)
    rate_limit_seconds: float = 1.0  # pause between Garmin calls
    rate_limit_backoff_seconds: int = 300  # wait after HTTP 429
    max_retries: int = 3
    sync_overlap_days: int = 1  # re-fetch N days before watermark for late uploads
    fit_download_enabled: bool = True
    fit_telemetry_max_points: int = 6000  # downsample telemetry above this
    auto_sync_on_startup: bool = True

    # --- Dashboard defaults ------------------------------------------------
    default_step_goal: int = 10000
    sleep_score_habit_threshold: int = 80
    weekly_intensity_target_minutes: int = 150
    default_timezone: str = "local"

    # --- Server ------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"

    @property
    def resolved_db_path(self) -> Path:
        return self.db_path or (self.data_dir / "fitdash.db")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.token_dir.mkdir(parents=True, exist_ok=True)
        if self.fit_cache_dir:
            self.fit_cache_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
