from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from app.config import Settings
from app.sync.engine import GarminSyncEngine
from app.sync.progress import SyncBroker
from app.util.timeutil import iso_date


def test_upsert_is_idempotent(db):
    rows = [{"ts": 1, "date": "2026-01-01", "hr": 60}, {"ts": 2, "date": "2026-01-01", "hr": 62}]
    db.upsert("intraday_hr", rows, ["ts"])
    db.upsert("intraday_hr", [{"ts": 2, "date": "2026-01-01", "hr": 70}], ["ts"])
    out = db.query("SELECT ts, hr FROM intraday_hr ORDER BY ts")
    assert out == [{"ts": 1, "hr": 60}, {"ts": 2, "hr": 70}]


def test_replace_for_key_drops_orphans(db):
    db.upsert("daily_summaries", [{"date": "2026-01-01", "updated_at": "x"}], ["date"])
    db.upsert("sleep_sessions", [{"date": "2026-01-01", "updated_at": "x"}], ["date"])
    stages = [{"date": "2026-01-01", "start_ts": 1, "end_ts": 2, "stage": 0}, {"date": "2026-01-01", "start_ts": 2, "end_ts": 3, "stage": 1}]
    db.replace_for_key("sleep_stages", "date", "2026-01-01", stages, ["date", "start_ts"])
    db.replace_for_key("sleep_stages", "date", "2026-01-01", stages[:1], ["date", "start_ts"])
    assert db.query_one("SELECT COUNT(*) AS n FROM sleep_stages")["n"] == 1


def _engine(db, authenticated=True):
    client = MagicMock()
    client.is_authenticated = authenticated
    settings = Settings(lookback_days=90, sync_overlap_days=1, data_dir=db.path.parent, token_dir=db.path.parent / "tok")
    return GarminSyncEngine(db, client, settings, SyncBroker())


def test_plan_initial_when_no_watermark(db):
    eng = _engine(db)
    plan = eng.plan()
    assert plan["mode"] == "initial"
    assert plan["days"] == 90
    assert plan["endDate"] == iso_date(date.today())


def test_plan_delta_uses_watermark_with_overlap(db):
    eng = _engine(db)
    db.execute("INSERT INTO sync_metadata (metric_domain, last_synced_date, status) VALUES ('daily', ?, 'ok')",
               (iso_date(date.today()),))
    plan = eng.plan()
    assert plan["mode"] == "delta"
    assert plan["days"] == 2  # yesterday (overlap) + today


def test_plan_lookback_override(db):
    eng = _engine(db)
    assert eng.plan(lookback_days=365)["days"] == 365


def test_watermark_moves_back_to_earliest_failure(db):
    eng = _engine(db)
    start, end = date(2026, 1, 1), date(2026, 1, 10)
    assert eng._compute_watermark(start, end, [], "ok") == "2026-01-10"
    assert eng._compute_watermark(start, end, ["2026-01-05", "2026-01-08"], "ok") == "2026-01-04"
    # never regress below an existing watermark
    db.execute("INSERT INTO sync_metadata (metric_domain, last_synced_date, status) VALUES ('daily', '2026-01-07', 'ok')")
    assert eng._compute_watermark(start, end, ["2026-01-05"], "ok") == "2026-01-07"
