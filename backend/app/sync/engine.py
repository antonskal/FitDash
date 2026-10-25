"""GarminSyncEngine — stateful incremental sync with initial backfill and delta watermarks.

Lifecycle
---------
1. `plan()` inspects `sync_metadata`. If no watermark exists this is an
   *initial* sync covering `lookback_days`; otherwise it is a *delta* sync
   from `last_synced_date - overlap` through today.
2. `start()` launches `_run()` in a daemon thread. Progress is streamed via
   `SyncBroker` to SSE subscribers.
3. `_run()` performs:
     a. range calls that cover the whole window in one request each
        (activity list, race predictions, weigh-ins, blood pressure, LT);
     b. a reverse-chronological per-day loop fetching daily/intraday/sleep/
        score domains, written in one transaction per day;
     c. activity enrichment for *new* activities only (HR zones, FIT
        telemetry, strength sets);
     d. watermark + run bookkeeping.

All writes are idempotent upserts keyed on natural primary keys, so re-running
any window is safe and simply refreshes partial data.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from app.config import Settings, get_settings
from app.db import Database, get_db
from app.garmin import mappers as M
from app.garmin.client import (
    GarminClient,
    GarminNotAuthenticated,
    GarminNotFound,
    GarminRateLimited,
    get_garmin_client,
)
from app.garmin.fit_parser import FitUnavailable, extract_fit_bytes, parse_fit
from app.sync.progress import SyncBroker
from app.util.timeutil import iso_date, iter_dates, now_iso, parse_date

log = logging.getLogger(__name__)

DOMAINS = ("daily", "intraday", "sleep", "scores", "activities")


class SyncAlreadyRunning(Exception):
    pass


class SyncCancelled(Exception):
    pass


class GarminSyncEngine:
    def __init__(self, db: Database, client: GarminClient, settings: Settings, broker: SyncBroker):
        self.db = db
        self.client = client
        self.settings = settings
        self.broker = broker
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._range_scores_ok: dict[str, bool] = {}

    # ------------------------------------------------------------ planning
    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def metadata(self) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM sync_metadata ORDER BY metric_domain")

    def watermark(self) -> str | None:
        rows = self.db.query("SELECT MIN(last_synced_date) AS wm FROM sync_metadata WHERE last_synced_date IS NOT NULL")
        return rows[0]["wm"] if rows and rows[0]["wm"] else None

    def plan(self, lookback_days: int | None = None, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        today = date.today()
        end = parse_date(end_date) if end_date else today
        wm = self.watermark()
        if start_date:
            mode = "manual"
            start = parse_date(start_date)
        elif wm is None:
            mode = "initial"
            start = end - timedelta(days=(lookback_days or self.settings.lookback_days) - 1)
        else:
            mode = "delta"
            start = min(parse_date(wm) - timedelta(days=self.settings.sync_overlap_days), end)
        return {"mode": mode, "startDate": iso_date(start), "endDate": iso_date(end),
                "days": (end - start).days + 1, "watermark": wm}

    # ------------------------------------------------------------- control
    def start(self, lookback_days: int | None = None, start_date: str | None = None,
              end_date: str | None = None, reprocess_fit: bool = False) -> dict[str, Any]:
        with self._lock:
            if self.is_running:
                raise SyncAlreadyRunning("A sync is already in progress")
            if not self.client.is_authenticated:
                raise GarminNotAuthenticated("Sign in to Garmin before syncing")
            plan = self.plan(lookback_days, start_date, end_date)
            self._cancel.clear()
            run_id = self._create_run(plan)
            self.broker.update(
                "progress", log_line=f"Starting {plan['mode']} sync {plan['startDate']} → {plan['endDate']} ({plan['days']} days)",
                run_id=run_id, mode=plan["mode"], status="running", phase="range", message="Preparing sync…",
                start_date=plan["startDate"], end_date=plan["endDate"], days_total=plan["days"], days_done=0,
                activities_total=0, activities_new=0, activities_done=0, errors=0, current_date=None,
                started_at=now_iso(), finished_at=None, error=None,
            )
            self._thread = threading.Thread(target=self._run, args=(run_id, plan, reprocess_fit), name="garmin-sync", daemon=True)
            self._thread.start()
            return {"runId": run_id, **plan}

    def cancel(self) -> bool:
        if not self.is_running:
            return False
        self._cancel.set()
        return True

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise SyncCancelled()

    # ------------------------------------------------------------- the run
    def _run(self, run_id: int, plan: dict[str, Any], reprocess_fit: bool) -> None:
        start, end = parse_date(plan["startDate"]), parse_date(plan["endDate"])
        failed_days: list[str] = []
        status, error_msg = "ok", None
        new_activities = 0
        try:
            self._set_domain_status("running", "Sync in progress")
            # a) whole-window range calls
            self._sync_ranges(start, end)
            activities = self._sync_activity_list(start, end)

            # b) per-day loop, newest first so the dashboard is useful early
            self.broker.update("progress", phase="daily", message="Fetching daily metrics…")
            for idx, d in enumerate(iter_dates(start, end, reverse=True), start=1):
                self._check_cancel()
                ds = iso_date(d)
                ok = self._sync_day(ds, idx, plan["days"])
                if not ok:
                    failed_days.append(ds)
                self.broker.update("progress", days_done=idx, current_date=ds)
                self.db.execute("UPDATE sync_runs SET days_done=? WHERE id=?", (idx, run_id))

            # c) activity enrichment (new ones only)
            new_activities = self._enrich_activities(activities, reprocess_fit)

        except SyncCancelled:
            status, error_msg = "cancelled", "Sync cancelled by user"
        except GarminRateLimited as exc:
            status, error_msg = "error", f"Garmin rate limit reached. Try again in ~{int(exc.retry_after_s // 60)} min."
        except GarminNotAuthenticated as exc:
            status, error_msg = "error", f"Garmin session lost: {exc}"
        except Exception as exc:  # noqa: BLE001
            log.exception("Sync run %s failed", run_id)
            status, error_msg = "error", f"{type(exc).__name__}: {exc}"

        # d) watermark + bookkeeping
        new_wm = self._compute_watermark(start, end, failed_days, status)
        with self.db.transaction() as conn:
            for domain in DOMAINS:
                conn.execute(
                    """INSERT INTO sync_metadata (metric_domain, last_synced_date, last_synced_timestamp, status, message)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(metric_domain) DO UPDATE SET
                         last_synced_date = COALESCE(excluded.last_synced_date, sync_metadata.last_synced_date),
                         last_synced_timestamp = excluded.last_synced_timestamp,
                         status = excluded.status, message = excluded.message""",
                    (domain, new_wm, now_iso(), status, error_msg),
                )
            conn.execute(
                "UPDATE sync_runs SET finished_at=?, status=?, message=?, activities_new=? WHERE id=?",
                (now_iso(), status, error_msg, new_activities, run_id),
            )
        summary = (
            f"Sync {status}: {plan['days'] - len(failed_days)}/{plan['days']} days, {new_activities} new activities"
            + (f", {len(failed_days)} days with errors" if failed_days else "")
        )
        self.broker.update("done" if status == "ok" else "error", log_line=error_msg or summary,
                           status=status, phase="finalize", message=error_msg or summary,
                           finished_at=now_iso(), error=error_msg, activities_new=new_activities)

    def _compute_watermark(self, start: date, end: date, failed: list[str], status: str) -> str | None:
        previous = self.watermark()
        if status == "ok" and not failed:
            return iso_date(end)
        if failed:
            earliest_failed = parse_date(min(failed))
            candidate = earliest_failed - timedelta(days=1)
        else:  # cancelled/errored before finishing: only advance if we finished nothing after wm
            candidate = parse_date(previous) if previous else None
        if candidate is None:
            return None if status != "ok" else iso_date(end)
        if previous and parse_date(previous) > candidate:
            return previous
        return iso_date(candidate) if candidate >= start else previous

    def _create_run(self, plan: dict[str, Any]) -> int:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO sync_runs (mode, start_date, end_date, started_at, status, days_total) VALUES (?,?,?,?,?,?)",
                (plan["mode"], plan["startDate"], plan["endDate"], now_iso(), "running", plan["days"]),
            )
            return int(cur.lastrowid)

    def _set_domain_status(self, status: str, message: str | None) -> None:
        with self.db.transaction() as conn:
            for domain in DOMAINS:
                conn.execute(
                    """INSERT INTO sync_metadata (metric_domain, status, message) VALUES (?, ?, ?)
                       ON CONFLICT(metric_domain) DO UPDATE SET status=excluded.status, message=excluded.message""",
                    (domain, status, message),
                )

    # ----------------------------------------------------------- fetch utils
    def _safe(self, label: str, fn: Callable[[], Any], *, allow_404: bool = True) -> Any:
        """Run one Garmin fetch; log + swallow per-metric failures (except rate-limit/auth)."""
        try:
            return fn()
        except (GarminRateLimited, GarminNotAuthenticated, SyncCancelled):
            raise
        except GarminNotFound:
            if allow_404:
                return None
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("%s failed: %s", label, exc)
            self.broker.update("log", log_line=f"⚠ {label}: {exc}", errors=self.broker.state.errors + 1)
            return None

    # ------------------------------------------------------------ range sync
    def _sync_ranges(self, start: date, end: date) -> None:
        api = self.client.api
        s, e = iso_date(start), iso_date(end)
        metrics: list[dict[str, Any]] = []

        self.broker.update("progress", message="Fetching race predictions, body composition, blood pressure…")
        rp = self._safe("race predictions", lambda: self.client.call(api.get_race_predictions, startdate=s, enddate=e, _type="daily"))
        metrics += M.map_race_predictions_range(rp)

        # Garmin caps weigh-in ranges; chunk by ~31 days.
        for cs, ce in _chunks(start, end, 31):
            self._check_cancel()
            w = self._safe("weigh-ins", lambda cs=cs, ce=ce: self.client.call(api.get_weigh_ins, iso_date(cs), iso_date(ce)))
            metrics += M.map_weigh_ins_range(w)
            bp = self._safe("blood pressure", lambda cs=cs, ce=ce: self.client.call(api.get_blood_pressure, iso_date(cs), iso_date(ce)))
            metrics += M.map_blood_pressure_range(bp)

        lt = self._safe("lactate threshold", lambda: self.client.call(api.get_lactate_threshold, latest=True))
        metrics += M.map_lactate_threshold_latest(lt)

        hill = self._safe("hill score range", lambda: self.client.call(api.get_hill_score, s, e))
        hill_rows = M.map_hill_range(hill)
        endurance = self._safe("endurance score range", lambda: self.client.call(api.get_endurance_score, s, e, "daily"))
        endurance_rows = M.map_endurance_range(endurance)
        metrics += hill_rows + endurance_rows
        # If range endpoints returned nothing we fall back to per-day calls in _sync_day.
        self._range_scores_ok = {"hill": bool(hill_rows), "endurance": bool(endurance_rows)}

        if metrics:
            self.db.upsert("daily_metrics", metrics, ["date", "metric"])
        self.broker.update("log", log_line=f"Range metrics: {len(metrics)} values")

    def _sync_activity_list(self, start: date, end: date) -> list[dict[str, Any]]:
        api = self.client.api
        self.broker.update("progress", message="Fetching activity list…")
        raw = self._safe("activity list", lambda: self.client.call(api.get_activities_by_date, iso_date(start), iso_date(end))) or []
        rows = [r for r in (M.map_activity(a) for a in raw) if r]
        if rows:
            existing = {r["activity_id"]: r for r in self.db.query(
                f"SELECT activity_id, fit_status FROM activities WHERE activity_id IN ({','.join('?' * len(rows))})",
                [r["activity_id"] for r in rows])}
            with self.db.transaction() as conn:
                for row in rows:
                    prev = existing.get(row["activity_id"])
                    if prev:
                        row["fit_status"] = prev["fit_status"]  # preserve enrichment state
                    else:
                        row["fit_status"] = "pending"
                self.db.upsert("activities", rows, ["activity_id"], conn=conn)
        self.broker.update("progress", activities_total=len(rows), log_line=f"Activities in window: {len(rows)}")
        return rows

    # -------------------------------------------------------------- per day
    def _sync_day(self, ds: str, idx: int, total: int) -> bool:
        api = self.client.api
        ok = True
        progress = f"[{idx}/{total} days]"

        def step(label: str) -> None:
            self.broker.update("progress", message=f"Syncing {ds}: {label} {progress}", current_date=ds)

        # --- daily summary (also yields the local UTC offset for step bucketing)
        step("Daily stats")
        stats = self._safe(f"{ds} daily stats", lambda: self.client.call(api.get_stats, ds)) or {}
        offset_ms = M.daily_local_offset_ms(stats)
        daily_row = M.map_daily_summary(ds, stats)

        # --- intraday
        step("Heart Rate")
        hr_payload = self._safe(f"{ds} heart rate", lambda: self.client.call(api.get_heart_rates, ds)) or {}
        hr_rows, hr_metrics = M.map_intraday_hr(ds, hr_payload)

        step("Steps")
        steps_payload = self._safe(f"{ds} steps", lambda: self.client.call(api.get_steps_data, ds)) or []
        steps_rows = M.map_hourly_steps(ds, steps_payload, offset_ms)

        step("Stress & Body Battery")
        stress_payload = self._safe(f"{ds} stress", lambda: self.client.call(api.get_stress_data, ds)) or {}
        stress_rows, bb_rows = M.map_intraday_stress(ds, stress_payload)

        step("Respiration")
        resp_payload = self._safe(f"{ds} respiration", lambda: self.client.call(api.get_respiration_data, ds)) or {}
        resp_rows = M.map_intraday_respiration(ds, resp_payload)

        # --- sleep
        step("Sleep")
        sleep_payload = self._safe(f"{ds} sleep", lambda: self.client.call(api.get_sleep_data, ds)) or {}
        sleep = M.map_sleep(ds, sleep_payload)

        step("HRV")
        hrv_payload = self._safe(f"{ds} hrv", lambda: self.client.call(api.get_hrv_data, ds))
        hrv_rows, hrv_metrics = M.map_hrv(ds, hrv_payload)

        # --- scores
        step("Readiness & Scores")
        metrics: list[dict[str, Any]] = hr_metrics + hrv_metrics
        metrics += M.map_training_readiness(ds, self._safe(f"{ds} training readiness", lambda: self.client.call(api.get_training_readiness, ds)))
        metrics += M.map_max_metrics(ds, self._safe(f"{ds} VO2 max", lambda: self.client.call(api.get_max_metrics, ds)))
        metrics += M.map_hydration(ds, self._safe(f"{ds} hydration", lambda: self.client.call(api.get_hydration_data, ds)))
        range_ok = self._range_scores_ok
        if not range_ok.get("hill"):
            metrics += M.map_hill(ds, self._safe(f"{ds} hill score", lambda: self.client.call(api.get_hill_score, ds)))
        if not range_ok.get("endurance"):
            metrics += M.map_endurance(ds, self._safe(f"{ds} endurance score", lambda: self.client.call(api.get_endurance_score, ds)))
        if ds == iso_date(date.today()) or idx == 1:
            metrics += M.map_training_status(ds, self._safe(f"{ds} training status", lambda: self.client.call(api.get_training_status, ds)))
            metrics += M.map_fitness_age(ds, self._safe(f"{ds} fitness age", lambda: self.client.call(api.get_fitnessage_data, ds)))

        if not stats and not hr_rows and not sleep["session"]:
            ok = False  # nothing at all came back for this day → treat as failed so we retry later

        # --- write everything for the day atomically
        with self.db.transaction() as conn:
            if daily_row:
                self.db.upsert("daily_summaries", [daily_row], ["date"], conn=conn)
            self.db.upsert("intraday_hr", hr_rows, ["ts"], conn=conn)
            if steps_rows:
                self.db.replace_for_key("hourly_steps", "date", ds, steps_rows, ["date", "hour"], conn=conn)
            self.db.upsert("intraday_stress", stress_rows, ["ts"], conn=conn)
            self.db.upsert("intraday_body_battery", bb_rows, ["ts"], conn=conn)
            self.db.upsert("intraday_respiration", resp_rows + sleep["respiration"], ["ts"], conn=conn)
            self.db.upsert("intraday_spo2", sleep["spo2"], ["ts"], conn=conn)
            self.db.upsert("hrv_readings", hrv_rows + sleep["hrv"], ["ts"], conn=conn)
            if sleep["session"]:
                sd = sleep["session"]["date"]
                self.db.upsert("sleep_sessions", [sleep["session"]], ["date"], conn=conn)
                self.db.replace_for_key("sleep_stages", "date", sd, sleep["stages"], ["date", "start_ts"], conn=conn)
                self.db.replace_for_key("sleep_movement", "date", sd, sleep["movement"], ["ts"], conn=conn)
            if metrics:
                self.db.upsert("daily_metrics", metrics, ["date", "metric"], conn=conn)
        return ok

    # ----------------------------------------------------------- activities
    def _enrich_activities(self, activities: list[dict[str, Any]], reprocess: bool) -> int:
        api = self.client.api
        ids = [a["activity_id"] for a in activities]
        if not ids:
            return 0
        rows = self.db.query(
            f"SELECT activity_id, sport_category, name, fit_status FROM activities WHERE activity_id IN ({','.join('?' * len(ids))})", ids)
        todo = [r for r in rows if reprocess or r["fit_status"] in ("pending", "error")]
        self.broker.update("progress", phase="activities", activities_new=len(todo), activities_done=0,
                           message=f"Processing {len(todo)} new activities…")
        done = 0
        for r in todo:
            self._check_cancel()
            aid = r["activity_id"]
            label = r["name"] or r["sport_category"]
            self.broker.update("progress", message=f"Activity {label} ({aid}): HR zones", activities_done=done)
            updates: dict[str, Any] = {"activity_id": aid, "updated_at": now_iso()}

            zones = self._safe(f"activity {aid} HR zones", lambda: self.client.call(api.get_activity_hr_in_timezones, str(aid)))
            updates.update(M.map_hr_zone_boundaries(zones))

            if r["sport_category"] == "strength":
                self.broker.update("progress", message=f"Activity {label} ({aid}): exercise sets")
                sets_payload = self._safe(f"activity {aid} exercise sets", lambda: self.client.call(api.get_activity_exercise_sets, aid))
                set_rows = M.map_exercise_sets(aid, sets_payload)
                if set_rows:
                    self.db.replace_for_key("strength_sets", "activity_id", aid, set_rows, ["activity_id", "set_index"])

            fit_status = "skipped"
            if self.settings.fit_download_enabled:
                self.broker.update("progress", message=f"Activity {label} ({aid}): downloading FIT")
                fit_status = self._ingest_fit(aid, r["sport_category"])
            updates["fit_status"] = fit_status
            updates["fit_parsed_at"] = now_iso() if fit_status == "parsed" else None
            self.db.upsert("activities", [updates], ["activity_id"])
            done += 1
            self.broker.update("progress", activities_done=done, log_line=f"✓ {label} ({aid}) → {fit_status}")
        return done

    def _ingest_fit(self, activity_id: int, category: str) -> str:
        api = self.client.api
        try:
            archive = self.client.call(api.download_activity, str(activity_id), dl_fmt=api.ActivityDownloadFormat.ORIGINAL)
        except GarminNotFound:
            return "unavailable"
        except (GarminRateLimited, GarminNotAuthenticated):
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("FIT download failed for %s: %s", activity_id, exc)
            return "error"
        try:
            fit_bytes = extract_fit_bytes(archive)
            parsed = parse_fit(fit_bytes, activity_id, self.settings.fit_telemetry_max_points)
        except FitUnavailable as exc:
            log.info("FIT unavailable for %s: %s", activity_id, exc)
            return "unavailable"

        if self.settings.fit_cache_dir:
            (self.settings.fit_cache_dir / f"{activity_id}.fit").write_bytes(fit_bytes)

        with self.db.transaction() as conn:
            self.db.replace_for_key("activity_telemetry_points", "activity_id", activity_id, parsed.points,
                                    ["activity_id", "elapsed_s"], conn=conn)
            self.db.replace_for_key("activity_laps", "activity_id", activity_id, parsed.laps, ["activity_id", "lap_index"], conn=conn)
            if parsed.sets and category == "strength":
                # API sets (with exercise names) take precedence; only fill from FIT when the API returned nothing.
                have = conn.execute("SELECT COUNT(*) AS n FROM strength_sets WHERE activity_id=?", (activity_id,)).fetchone()["n"]
                if not have:
                    self.db.upsert("strength_sets", parsed.sets, ["activity_id", "set_index"], conn=conn)
            if parsed.session.get("normalized_power") is not None:
                conn.execute("UPDATE activities SET normalized_power=COALESCE(normalized_power, ?) WHERE activity_id=?",
                             (parsed.session["normalized_power"], activity_id))
        return "parsed"


def _chunks(start: date, end: date, size: int):
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=size - 1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


@lru_cache
def get_sync_broker() -> SyncBroker:
    return SyncBroker()


@lru_cache
def get_sync_engine() -> GarminSyncEngine:
    return GarminSyncEngine(get_db(), get_garmin_client(), get_settings(), get_sync_broker())
