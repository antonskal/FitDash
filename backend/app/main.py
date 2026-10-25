"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload
The built frontend (frontend/dist) is served from `/` when present so the whole
app is a single local process.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import routes_activities, routes_auth, routes_metrics, routes_sync
from app.config import get_settings
from app.db import get_db
from app.garmin import get_garmin_client
from app.sync import get_sync_engine
from app.sync.engine import SyncAlreadyRunning

log = logging.getLogger("fitdash")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    get_db()  # creates schema / enables WAL
    client = get_garmin_client()
    engine = get_sync_engine()
    restored = client.try_restore_session()
    log.info("Garmin session restored: %s", restored)
    if restored and settings.auto_sync_on_startup and engine.watermark() is not None:
        # Delta sync on launch. Initial syncs are user-triggered from the onboarding modal
        # so the user can pick the lookback window first.
        try:
            plan = engine.start()
            log.info("Auto delta sync started: %s", plan)
        except SyncAlreadyRunning:
            pass
        except Exception as exc:  # noqa: BLE001
            log.warning("Auto sync failed to start: %s", exc)
    yield
    engine.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FitDash", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_auth.router)
    app.include_router(routes_sync.router)
    app.include_router(routes_metrics.router)
    app.include_router(routes_activities.router)

    @app.get("/api/health", tags=["meta"])
    def health():
        return {"ok": True}

    dist: Path = settings.frontend_dist
    if dist.exists() and (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
