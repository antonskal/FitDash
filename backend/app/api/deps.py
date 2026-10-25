"""FastAPI dependency providers + shared query-param validation."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, Query

from app.config import Settings, get_settings
from app.db import Database, get_db
from app.garmin import GarminClient, get_garmin_client
from app.sync import GarminSyncEngine, get_sync_engine
from app.sync.engine import get_sync_broker
from app.sync.progress import SyncBroker
from app.util.timeutil import iso_date, parse_date


def db() -> Database:
    return get_db()


def settings() -> Settings:
    return get_settings()


def garmin() -> GarminClient:
    return get_garmin_client()


def engine() -> GarminSyncEngine:
    return get_sync_engine()


def broker() -> SyncBroker:
    return get_sync_broker()


def validate_date(value: str, name: str = "date") -> str:
    try:
        return iso_date(parse_date(value))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{name} must be YYYY-MM-DD") from exc


def date_range(
    start: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    end: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    days: int = Query(30, ge=1, le=3660, description="Fallback window length when start is omitted"),
) -> tuple[str, str]:
    end_d = parse_date(validate_date(end, "end")) if end else date.today()
    start_d = parse_date(validate_date(start, "start")) if start else end_d - timedelta(days=days - 1)
    if start_d > end_d:
        raise HTTPException(status_code=422, detail="start must be <= end")
    return iso_date(start_d), iso_date(end_d)
