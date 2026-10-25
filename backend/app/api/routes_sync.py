from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api import deps
from app.config import Settings
from app.db import Database
from app.garmin.client import GarminNotAuthenticated
from app.sync import GarminSyncEngine, SyncBroker
from app.sync.engine import SyncAlreadyRunning

router = APIRouter(prefix="/api/sync", tags=["sync"])


class StartSyncRequest(BaseModel):
    lookbackDays: int | None = Field(None, ge=1, le=3660)
    startDate: str | None = None
    endDate: str | None = None
    reprocessFit: bool = False


@router.get("/status")
def status(engine: GarminSyncEngine = Depends(deps.engine), broker: SyncBroker = Depends(deps.broker),
           db: Database = Depends(deps.db), settings: Settings = Depends(deps.settings)):
    metadata = engine.metadata()
    last_run = db.query_one("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1")
    watermark = engine.watermark()
    plan = engine.plan() if engine.client.is_authenticated else None
    return {
        "live": broker.snapshot(),
        "isRunning": engine.is_running,
        "isFirstSync": watermark is None,
        "watermark": watermark,
        "lastSyncedAt": max((m["last_synced_timestamp"] or "" for m in metadata), default=None) or None,
        "metadata": metadata,
        "lastRun": last_run,
        "plan": plan,
        "defaults": {"lookbackDays": settings.lookback_days},
    }


@router.post("/start")
def start(body: StartSyncRequest, engine: GarminSyncEngine = Depends(deps.engine)):
    try:
        if body.startDate:
            deps.validate_date(body.startDate, "startDate")
        if body.endDate:
            deps.validate_date(body.endDate, "endDate")
        return engine.start(lookback_days=body.lookbackDays, start_date=body.startDate, end_date=body.endDate,
                            reprocess_fit=body.reprocessFit)
    except SyncAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GarminNotAuthenticated as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/cancel")
def cancel(engine: GarminSyncEngine = Depends(deps.engine)):
    return {"cancelled": engine.cancel()}


@router.get("/runs")
def runs(db: Database = Depends(deps.db), limit: int = 20):
    return db.query("SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,))


@router.get("/events")
async def events(request: Request, broker: SyncBroker = Depends(deps.broker)):
    """Server-Sent Events stream of sync progress. Emits the current snapshot first."""
    sid, queue = broker.subscribe()

    async def gen():
        try:
            yield _sse({"type": "snapshot", **broker.snapshot()})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield _sse(payload)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            broker.unsubscribe(sid)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


def _sse(payload: dict) -> str:
    return f"event: {payload.get('type', 'progress')}\ndata: {json.dumps(payload)}\n\n"
