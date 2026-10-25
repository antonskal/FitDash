"""Read-side queries for the dashboard (daily, intraday, sleep, overview)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.db import Database
from app.garmin import mappers as M
from app.util.timeutil import iso_date, parse_date

# Intraday downsampling buckets (ms) by window length (days).
_BUCKETS = ((2, 0), (14, 5 * 60_000), (45, 15 * 60_000), (120, 60 * 60_000), (10_000, 3 * 60 * 60_000))


def bucket_for(start: str, end: str) -> int:
    days = (parse_date(end) - parse_date(start)).days + 1
    for max_days, bucket in _BUCKETS:
        if days <= max_days:
            return bucket
    return _BUCKETS[-1][1]


def _series(db: Database, table: str, col: str, start: str, end: str, bucket: int,
            where_extra: str = "") -> list[list[float]]:
    if bucket == 0:
        rows = db.query(f"SELECT ts, {col} AS v FROM {table} WHERE date BETWEEN ? AND ? {where_extra} ORDER BY ts", (start, end))
    else:
        rows = db.query(
            f"SELECT (ts / {bucket}) * {bucket} AS ts, AVG({col}) AS v FROM {table} "
            f"WHERE date BETWEEN ? AND ? {where_extra} GROUP BY ts / {bucket} ORDER BY ts",
            (start, end),
        )
    return [[r["ts"], round(r["v"], 2) if isinstance(r["v"], float) else r["v"]] for r in rows]


def intraday(db: Database, start: str, end: str) -> dict[str, Any]:
    bucket = bucket_for(start, end)
    return {
        "bucketMs": bucket,
        "hr": _series(db, "intraday_hr", "hr", start, end, bucket),
        "stress": _series(db, "intraday_stress", "stress", start, end, bucket, "AND stress >= 0"),
        "bodyBattery": _series(db, "intraday_body_battery", "level", start, end, bucket),
        "respiration": _series(db, "intraday_respiration", "brpm", start, end, bucket),
        "spo2": _series(db, "intraday_spo2", "spo2", start, end, bucket),
        "hrv": _series(db, "hrv_readings", "hrv", start, end, bucket),
    }


def daily(db: Database, start: str, end: str) -> list[dict[str, Any]]:
    rows = db.query(
        """SELECT d.*, s.sleep_score, s.total_sleep_s, s.deep_s, s.light_s, s.rem_s, s.awake_s,
                  s.sleep_start_ts, s.sleep_end_ts, s.avg_hrv AS sleep_avg_hrv,
                  s.avg_spo2 AS sleep_avg_spo2, s.lowest_spo2 AS sleep_lowest_spo2,
                  s.avg_respiration AS sleep_avg_respiration, s.avg_movement AS sleep_avg_movement,
                  s.skin_temp_dev_c AS sleep_skin_temp_dev_c, s.skin_temp_dev_f AS sleep_skin_temp_dev_f,
                  s.restless_moments, s.awake_count
           FROM daily_summaries d LEFT JOIN sleep_sessions s ON s.date = d.date
           WHERE d.date BETWEEN ? AND ? ORDER BY d.date""",
        (start, end),
    )
    # Fold in a few sparse metrics that are useful as daily trends.
    wanted = (M.M_RHR_7D, M.M_HRV_LAST_NIGHT, M.M_TRAINING_READINESS, M.M_VO2MAX_RUN, M.M_WEIGHT, M.M_HYDRATION,
              M.M_HYDRATION_GOAL, M.M_ENDURANCE, M.M_HILL, M.M_WEEKLY_LOAD)
    mrows = db.query(
        f"SELECT date, metric, value FROM daily_metrics WHERE date BETWEEN ? AND ? AND metric IN ({','.join('?' * len(wanted))})",
        (start, end, *wanted),
    )
    by_date: dict[str, dict[str, float]] = {}
    for r in mrows:
        by_date.setdefault(r["date"], {})[r["metric"]] = r["value"]
    for row in rows:
        row["metrics"] = by_date.get(row["date"], {})
    # Days with sleep but no daily summary (rare) — still surface them.
    have = {r["date"] for r in rows}
    extra = db.query("SELECT * FROM sleep_sessions WHERE date BETWEEN ? AND ? ORDER BY date", (start, end))
    for s in extra:
        if s["date"] not in have:
            rows.append({"date": s["date"], "sleep_score": s["sleep_score"], "total_sleep_s": s["total_sleep_s"],
                         "deep_s": s["deep_s"], "light_s": s["light_s"], "rem_s": s["rem_s"], "awake_s": s["awake_s"],
                         "sleep_start_ts": s["sleep_start_ts"], "sleep_end_ts": s["sleep_end_ts"], "metrics": by_date.get(s["date"], {})})
    rows.sort(key=lambda r: r["date"])
    return rows


def hourly_steps(db: Database, start: str, end: str) -> list[dict[str, Any]]:
    return db.query("SELECT date, hour, steps FROM hourly_steps WHERE date BETWEEN ? AND ? ORDER BY date, hour", (start, end))


def sleep_detail(db: Database, date: str) -> dict[str, Any]:
    session = db.query_one("SELECT * FROM sleep_sessions WHERE date = ?", (date,))
    if not session:
        # Try the following calendar day (sleep attributed to wake date).
        nxt = iso_date(parse_date(date) + timedelta(days=1))
        session = db.query_one("SELECT * FROM sleep_sessions WHERE date = ?", (nxt,))
    if not session:
        return {"session": None, "stages": [], "movement": [], "spo2": [], "respiration": [], "hrv": [], "hr": []}
    d = session["date"]
    s_ts, e_ts = session["sleep_start_ts"], session["sleep_end_ts"]
    stages = db.query("SELECT start_ts, end_ts, stage FROM sleep_stages WHERE date = ? ORDER BY start_ts", (d,))
    movement = db.query("SELECT ts, level FROM sleep_movement WHERE date = ? ORDER BY ts", (d,))
    rng = (s_ts - 10 * 60_000, e_ts + 10 * 60_000) if s_ts and e_ts else (0, 0)
    spo2 = db.query("SELECT ts, spo2 AS v FROM intraday_spo2 WHERE ts BETWEEN ? AND ? ORDER BY ts", rng)
    resp = db.query("SELECT ts, brpm AS v FROM intraday_respiration WHERE ts BETWEEN ? AND ? ORDER BY ts", rng)
    hrv = db.query("SELECT ts, hrv AS v FROM hrv_readings WHERE ts BETWEEN ? AND ? ORDER BY ts", rng)
    hr = db.query("SELECT ts, hr AS v FROM intraday_hr WHERE ts BETWEEN ? AND ? ORDER BY ts", rng)
    return {
        "session": session,
        "stages": [[r["start_ts"], r["end_ts"], r["stage"]] for r in stages],
        "movement": [[r["ts"], r["level"]] for r in movement],
        "spo2": [[r["ts"], r["v"]] for r in spo2],
        "respiration": [[r["ts"], r["v"]] for r in resp],
        "hrv": [[r["ts"], r["v"]] for r in hrv],
        "hr": [[r["ts"], r["v"]] for r in hr],
    }


def latest_metric(db: Database, metric: str, on_or_before: str, max_age_days: int | None = None) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT date, value, text_value FROM daily_metrics WHERE metric = ? AND date <= ? AND (value IS NOT NULL OR text_value IS NOT NULL) "
        "ORDER BY date DESC LIMIT 1",
        (metric, on_or_before),
    )
    if not row:
        return None
    if max_age_days is not None and (parse_date(on_or_before) - parse_date(row["date"])).days > max_age_days:
        return None
    return {"value": row["value"], "text": row["text_value"], "date": row["date"]}


def metric_history(db: Database, metric: str, start: str, end: str) -> list[list[Any]]:
    rows = db.query("SELECT date, value FROM daily_metrics WHERE metric = ? AND date BETWEEN ? AND ? AND value IS NOT NULL ORDER BY date",
                    (metric, start, end))
    return [[r["date"], r["value"]] for r in rows]


def overview(db: Database, date: str, step_goal_default: int) -> dict[str, Any]:
    """Everything the 'At-a-Glance' row needs for a single inspection date."""
    day = db.query_one("SELECT * FROM daily_summaries WHERE date = ?", (date,)) or {}
    sleep = db.query_one("SELECT * FROM sleep_sessions WHERE date = ?", (date,)) or {}
    week_start = iso_date(parse_date(date) - timedelta(days=6))
    rhr7 = db.query_one("SELECT AVG(resting_hr) AS v FROM daily_summaries WHERE date BETWEEN ? AND ? AND resting_hr IS NOT NULL",
                        (week_start, date))
    hrv7 = db.query_one(
        "SELECT AVG(value) AS v FROM daily_metrics WHERE metric = ? AND date BETWEEN ? AND ? AND value IS NOT NULL",
        (M.M_HRV_LAST_NIGHT, week_start, date))
    bb_latest = db.query_one(
        "SELECT level, ts FROM intraday_body_battery WHERE date = ? ORDER BY ts DESC LIMIT 1", (date,))
    lm = lambda m, age=None: latest_metric(db, m, date, age)  # noqa: E731
    return {
        "date": date,
        "readiness": {
            "sleepScore": sleep.get("sleep_score"),
            "sleepQualifier": sleep.get("score_qualifier"),
            "totalSleepS": sleep.get("total_sleep_s"),
            "bodyBattery": {
                "current": (bb_latest or {}).get("level", day.get("body_battery_most_recent")),
                "charged": day.get("body_battery_charged"),
                "drained": day.get("body_battery_drained"),
                "highest": day.get("body_battery_highest"),
                "lowest": day.get("body_battery_lowest"),
                "atWake": day.get("body_battery_at_wake"),
            },
            "trainingReadiness": lm(M.M_TRAINING_READINESS, 1),
            "trainingReadinessLevel": lm(M.M_TRAINING_READINESS_LEVEL, 1),
            "recoveryTimeH": lm(M.M_RECOVERY_TIME_H, 1),
            "hrv": {
                "lastNight": (lm(M.M_HRV_LAST_NIGHT, 1) or {}).get("value", sleep.get("avg_hrv")),
                "weeklyAvg": (lm(M.M_HRV_WEEKLY_AVG, 1) or {}).get("value"),
                "sevenDayMean": round(hrv7["v"], 1) if hrv7 and hrv7["v"] else None,
                "status": (lm(M.M_HRV_STATUS, 1) or {}).get("text"),
                "baselineLow": (lm(M.M_HRV_BASELINE_LOW, 7) or {}).get("value"),
                "baselineHigh": (lm(M.M_HRV_BASELINE_HIGH, 7) or {}).get("value"),
            },
            "restingHr": day.get("resting_hr"),
            "restingHr7d": round(rhr7["v"], 1) if rhr7 and rhr7["v"] else None,
            "avgStress": day.get("avg_stress"),
            "trainingStatus": lm(M.M_TRAINING_STATUS, 14),
            "weeklyLoad": lm(M.M_WEEKLY_LOAD, 14),
            "acwr": lm(M.M_ACWR, 14),
        },
        "performance": {
            "vo2maxRunning": lm(M.M_VO2MAX_RUN),
            "vo2maxCycling": lm(M.M_VO2MAX_CYCLE),
            "fitnessAge": lm(M.M_FITNESS_AGE),
            "enduranceScore": lm(M.M_ENDURANCE),
            "hillScore": lm(M.M_HILL),
            "hillStrength": lm(M.M_HILL_STRENGTH),
            "hillEndurance": lm(M.M_HILL_ENDURANCE),
            "lactateThresholdHr": lm(M.M_LT_HR),
            "lactateThresholdSpeedMps": lm(M.M_LT_SPEED),
            "race": {
                "5k": lm(M.M_RACE_5K), "10k": lm(M.M_RACE_10K), "half": lm(M.M_RACE_HALF), "marathon": lm(M.M_RACE_FULL),
            },
        },
        "daily": {
            "steps": day.get("total_steps"),
            "stepGoal": day.get("step_goal") or step_goal_default,
            "distanceM": day.get("total_distance_m"),
            "activeKcal": day.get("active_kcal"),
            "restingKcal": day.get("bmr_kcal"),
            "totalKcal": day.get("total_kcal"),
            "moderateMin": day.get("moderate_intensity_min"),
            "vigorousMin": day.get("vigorous_intensity_min"),
            "floorsUp": day.get("floors_ascended"),
            "hydrationMl": (lm(M.M_HYDRATION, 0) or {}).get("value"),
            "hydrationGoalMl": (lm(M.M_HYDRATION_GOAL, 0) or {}).get("value"),
            "sweatLossMl": (lm(M.M_SWEAT_LOSS, 0) or {}).get("value"),
            "bloodPressure": {"systolic": lm(M.M_BP_SYS), "diastolic": lm(M.M_BP_DIA), "pulse": lm(M.M_BP_PULSE)},
            "body": {
                "weightKg": lm(M.M_WEIGHT), "bmi": lm(M.M_BMI), "bodyFatPct": lm(M.M_BODY_FAT),
                "bodyWaterPct": lm(M.M_BODY_WATER), "muscleMassKg": lm(M.M_MUSCLE_MASS), "boneMassKg": lm(M.M_BONE_MASS),
            },
            "spo2Avg": day.get("avg_spo2"),
            "spo2Lowest": day.get("lowest_spo2"),
            "respirationAvg": day.get("avg_respiration"),
            "skinTempDevC": day.get("avg_skin_temp_dev_c") if day.get("avg_skin_temp_dev_c") is not None else sleep.get("skin_temp_dev_c"),
            "skinTempDevF": day.get("avg_skin_temp_dev_f") if day.get("avg_skin_temp_dev_f") is not None else sleep.get("skin_temp_dev_f"),
        },
    }


def data_bounds(db: Database) -> dict[str, Any]:
    d = db.query_one("SELECT MIN(date) AS lo, MAX(date) AS hi, COUNT(*) AS n FROM daily_summaries") or {}
    a = db.query_one("SELECT COUNT(*) AS n FROM activities") or {}
    return {"firstDate": d.get("lo"), "lastDate": d.get("hi"), "days": d.get("n", 0), "activities": a.get("n", 0)}
