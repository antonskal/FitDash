from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import deps
from app.db import Database
from app.services import activities as svc

router = APIRouter(prefix="/api/activities", tags=["activities"])


@router.get("")
def list_(rng: tuple[str, str] = Depends(deps.date_range), category: str | None = None,
          q: str | None = Query(None, max_length=80), limit: int = Query(500, ge=1, le=5000),
          db: Database = Depends(deps.db)):
    start, end = rng
    return {"start": start, "end": end, "activities": svc.list_activities(db, start, end, category, q, limit),
            "categories": svc.categories_summary(db, start, end)}


@router.get("/{activity_id}")
def detail(activity_id: int, db: Database = Depends(deps.db)):
    d = svc.activity_detail(db, activity_id)
    if not d:
        raise HTTPException(status_code=404, detail="Activity not found")
    return d
