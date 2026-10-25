from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.config import Settings
from app.db import Database
from app.services import calendar as calendar_svc
from app.services import metrics as svc
from app.util.timeutil import iso_date

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/settings")
def settings_(settings: Settings = Depends(deps.settings), db: Database = Depends(deps.db)):
    return {
        "stepGoal": settings.default_step_goal,
        "sleepScoreHabitThreshold": settings.sleep_score_habit_threshold,
        "weeklyIntensityTargetMin": settings.weekly_intensity_target_minutes,
        "defaultTimezone": settings.default_timezone,
        "fitDownloadEnabled": settings.fit_download_enabled,
        "bounds": svc.data_bounds(db),
    }


@router.get("/overview")
def overview(date_: str | None = Query(None, alias="date"), db: Database = Depends(deps.db),
             settings: Settings = Depends(deps.settings)):
    d = deps.validate_date(date_) if date_ else iso_date(date.today())
    return svc.overview(db, d, settings.default_step_goal)


@router.get("/daily")
def daily(rng: tuple[str, str] = Depends(deps.date_range), db: Database = Depends(deps.db)):
    start, end = rng
    return {"start": start, "end": end, "days": svc.daily(db, start, end)}


@router.get("/intraday")
def intraday(rng: tuple[str, str] = Depends(deps.date_range), db: Database = Depends(deps.db)):
    start, end = rng
    return {"start": start, "end": end, **svc.intraday(db, start, end)}


@router.get("/steps/hourly")
def steps_hourly(rng: tuple[str, str] = Depends(deps.date_range), db: Database = Depends(deps.db)):
    start, end = rng
    return {"start": start, "end": end, "cells": svc.hourly_steps(db, start, end)}


@router.get("/sleep/detail")
def sleep_detail(date_: str = Query(..., alias="date"), db: Database = Depends(deps.db)):
    return svc.sleep_detail(db, deps.validate_date(date_))


@router.get("/metrics/{metric}")
def metric_history(metric: str, rng: tuple[str, str] = Depends(deps.date_range), db: Database = Depends(deps.db)):
    start, end = rng
    return {"metric": metric, "points": svc.metric_history(db, metric, start, end)}


@router.get("/calendar")
def calendar(rng: tuple[str, str] = Depends(deps.date_range), db: Database = Depends(deps.db),
             settings: Settings = Depends(deps.settings)):
    start, end = rng
    return calendar_svc.calendar(db, start, end, settings.default_step_goal)
