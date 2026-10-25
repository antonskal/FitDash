"""Offline demo seed — generates a year of plausible Garmin-like telemetry.

This is NOT the primary data path; it exists so the UI can be developed and
reviewed without a Garmin account. Usage:

    python -m app.demo.seed --days 365 --reset
"""

from __future__ import annotations

import argparse
import math
import random
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from app.config import get_settings
from app.db import Database, get_db
from app.garmin import mappers as M
from app.util.timeutil import iso_date, now_iso, to_epoch_ms

TZ_OFFSET_H = -4  # America/New_York (DST) for demo purposes
CENTER = (40.0150, -105.2705)  # Boulder, CO


def _local_dt(d: date, hh: int, mm: int = 0) -> datetime:
    """Local wall-clock time on date `d` expressed as an aware UTC datetime."""
    naive = datetime.combine(d, time(hh % 24, mm)) + timedelta(days=hh // 24)
    return (naive - timedelta(hours=TZ_OFFSET_H)).replace(tzinfo=UTC)


def seed(db: Database, days: int, reset: bool, rng: random.Random) -> None:
    today = date.today()
    start = today - timedelta(days=days - 1)
    if reset:
        with db.transaction() as conn:
            for t in ("activity_telemetry_points", "activity_laps", "strength_sets", "activities", "sleep_stages",
                      "sleep_movement", "sleep_sessions", "intraday_hr", "intraday_stress", "intraday_body_battery",
                      "intraday_respiration", "intraday_spo2", "hrv_readings", "hourly_steps", "daily_metrics",
                      "daily_summaries", "sync_runs", "sync_metadata"):
                conn.execute(f"DELETE FROM {t}")

    fitness = 0.0  # slowly improving
    weight = 78.0
    aid = 90_000_000_000
    strength_cycle = 0
    plan = _weekly_plan()

    for i in range(days):
        d = start + timedelta(days=i)
        ds = iso_date(d)
        fitness += rng.uniform(-0.05, 0.12)
        weight += rng.uniform(-0.15, 0.1)
        dow = d.weekday()
        workouts = plan[dow]
        if rng.random() < 0.15:
            workouts = []  # rest/skip day
        rest_day = not workouts

        # --- sleep (attributed to wake day `d`)
        bed_h = 22 + rng.uniform(0.3, 1.8) + (0.8 if dow in (4, 5) else 0)
        sleep_len = rng.uniform(6.2, 8.4) - (0.6 if dow in (4, 5) else 0)
        sleep_start = _local_dt(d - timedelta(days=1), int(bed_h), int((bed_h % 1) * 60))
        sleep_end = sleep_start + timedelta(hours=sleep_len)
        sleep = _make_sleep(ds, sleep_start, sleep_end, rng)
        sleep_score = sleep["session"]["sleep_score"]

        # --- activities
        day_acts: list[dict[str, Any]] = []
        telemetry: dict[int, list[dict[str, Any]]] = {}
        laps: dict[int, list[dict[str, Any]]] = {}
        sets: dict[int, list[dict[str, Any]]] = {}
        for w in workouts:
            aid += 1
            start_dt = _local_dt(d, w["hour"], rng.randint(0, 45))
            act, pts, lp, st = _make_activity(aid, ds, start_dt, w["category"], fitness, rng, strength_cycle)
            if w["category"] == "strength":
                strength_cycle += 1
            day_acts.append(act)
            if pts:
                telemetry[aid] = pts
            if lp:
                laps[aid] = lp
            if st:
                sets[aid] = st

        # --- intraday + daily summary
        intraday = _make_intraday(ds, d, sleep_start, sleep_end, day_acts, rng)
        active_kcal = sum((a["calories"] or 0) for a in day_acts) + rng.uniform(250, 450)
        steps = int(rng.gauss(7500 if rest_day else 11000, 2200)) + sum(a.get("steps") or 0 for a in day_acts) // 3
        steps = max(1500, steps)
        rhr = int(58 - fitness * 0.15 + rng.uniform(-2.5, 2.5) + (3 if sleep_score < 65 else 0))
        hr_vals = [p["hr"] for p in intraday["hr"]]
        stress_vals = [p["stress"] for p in intraday["stress"] if p["stress"] >= 0]
        daily = {
            "date": ds,
            "wellness_start_ts": to_epoch_ms(_local_dt(d, 0)),
            "wellness_end_ts": to_epoch_ms(_local_dt(d, 24)),
            "total_steps": steps, "step_goal": 10000, "total_distance_m": steps * 0.78,
            "active_kcal": round(active_kcal), "bmr_kcal": round(1750 + rng.uniform(-30, 30)),
            "total_kcal": None,
            "moderate_intensity_min": int(sum((a.get("moderate_min") or 0) for a in day_acts) + rng.randint(0, 15)),
            "vigorous_intensity_min": int(sum((a.get("vigorous_min") or 0) for a in day_acts)),
            "intensity_goal_min": 150,
            "floors_ascended": round(rng.uniform(4, 22), 1), "floors_descended": round(rng.uniform(3, 20), 1),
            "highly_active_s": int(sum((a["duration_s"] or 0) for a in day_acts)), "active_s": int(rng.uniform(5000, 9000)),
            "sedentary_s": int(rng.uniform(30000, 45000)), "sleeping_s": sleep["session"]["total_sleep_s"],
            "resting_hr": rhr, "min_hr": min(hr_vals), "max_hr": max(hr_vals),
            "avg_stress": int(sum(stress_vals) / len(stress_vals)) if stress_vals else None,
            "max_stress": max(stress_vals) if stress_vals else None,
            "stress_duration_s": None, "rest_stress_s": None, "low_stress_s": None, "medium_stress_s": None, "high_stress_s": None,
            "body_battery_charged": intraday["bb_charged"], "body_battery_drained": intraday["bb_drained"],
            "body_battery_highest": intraday["bb_high"], "body_battery_lowest": intraday["bb_low"],
            "body_battery_at_wake": intraday["bb_wake"], "body_battery_most_recent": intraday["bb_last"],
            "avg_spo2": round(rng.uniform(94.5, 97.5), 1), "lowest_spo2": round(rng.uniform(88, 93), 0),
            "avg_respiration": round(rng.uniform(13.5, 16.5), 1), "lowest_respiration": round(rng.uniform(10, 12.5), 1),
            "highest_respiration": round(rng.uniform(19, 24), 1),
            "avg_skin_temp_dev_c": round(rng.gauss(0, 0.35), 2), "avg_skin_temp_dev_f": None,
            "updated_at": now_iso(),
        }
        daily["total_kcal"] = daily["active_kcal"] + daily["bmr_kcal"]
        daily["avg_skin_temp_dev_f"] = round(daily["avg_skin_temp_dev_c"] * 1.8, 2)
        _stress_buckets(daily, stress_vals)

        # --- sparse metrics
        hrv_last = round(rng.gauss(52 + fitness * 0.2 - (6 if sleep_score < 65 else 0), 5), 0)
        readiness = int(min(100, max(5, 0.5 * sleep_score + 0.3 * min(100, hrv_last * 1.6) + rng.uniform(-8, 12) - (10 if not rest_day else 0))))
        metrics = [m for m in (
            M.metric(ds, M.M_RHR_7D, rhr + rng.uniform(-1, 1)),
            M.metric(ds, M.M_HRV_LAST_NIGHT, hrv_last),
            M.metric(ds, M.M_HRV_WEEKLY_AVG, round(hrv_last + rng.uniform(-3, 3))),
            M.metric(ds, M.M_HRV_STATUS, None, text=rng.choice(["BALANCED", "BALANCED", "BALANCED", "LOW", "UNBALANCED"])),
            M.metric(ds, M.M_HRV_BASELINE_LOW, 44), M.metric(ds, M.M_HRV_BASELINE_HIGH, 60),
            M.metric(ds, M.M_TRAINING_READINESS, readiness),
            M.metric(ds, M.M_TRAINING_READINESS_LEVEL, None, text="HIGH" if readiness >= 70 else "MODERATE" if readiness >= 45 else "LOW"),
            M.metric(ds, M.M_RECOVERY_TIME_H, round(rng.uniform(0, 36) if not rest_day else rng.uniform(0, 8))),
            M.metric(ds, M.M_VO2MAX_RUN, round(49.5 + fitness * 0.08, 1)),
            M.metric(ds, M.M_VO2MAX_CYCLE, round(52.0 + fitness * 0.06, 1)),
            M.metric(ds, M.M_FITNESS_AGE, round(31 - fitness * 0.03, 1)),
            M.metric(ds, M.M_ENDURANCE, round(6200 + fitness * 12 + rng.uniform(-40, 40))),
            M.metric(ds, M.M_HILL, round(62 + fitness * 0.1 + rng.uniform(-1, 1))),
            M.metric(ds, M.M_HILL_STRENGTH, round(58 + fitness * 0.08)), M.metric(ds, M.M_HILL_ENDURANCE, round(66 + fitness * 0.1)),
            M.metric(ds, M.M_HYDRATION, round(rng.uniform(1400, 3200), -1)), M.metric(ds, M.M_HYDRATION_GOAL, 2800),
            M.metric(ds, M.M_SWEAT_LOSS, round(sum((a["duration_s"] or 0) for a in day_acts) * 0.25)),
            M.metric(ds, M.M_TRAINING_STATUS, None, text=rng.choice(["Productive", "Maintaining", "Productive", "Recovery"])),
            M.metric(ds, M.M_WEEKLY_LOAD, round(380 + fitness * 3 + rng.uniform(-60, 60))),
            M.metric(ds, M.M_ACWR, round(rng.uniform(0.8, 1.3), 2)),
        ) if m]
        if dow == 0 or i == 0:  # weekly race predictions + LT
            base5k = 22 * 60 - fitness * 2.0
            metrics += [m for m in (
                M.metric(ds, M.M_RACE_5K, round(base5k)), M.metric(ds, M.M_RACE_10K, round(base5k * 2.08)),
                M.metric(ds, M.M_RACE_HALF, round(base5k * 4.6)), M.metric(ds, M.M_RACE_FULL, round(base5k * 9.7)),
                M.metric(ds, M.M_LT_HR, round(168 + fitness * 0.02)), M.metric(ds, M.M_LT_SPEED, round(3.55 + fitness * 0.003, 3)),
            ) if m]
        if dow in (0, 3):  # weigh-ins twice a week
            metrics += [m for m in (
                M.metric(ds, M.M_WEIGHT, round(weight, 1)), M.metric(ds, M.M_BMI, round(weight / (1.80 ** 2), 1)),
                M.metric(ds, M.M_BODY_FAT, round(16.5 - fitness * 0.01 + rng.uniform(-0.4, 0.4), 1)),
                M.metric(ds, M.M_BODY_WATER, round(58 + rng.uniform(-1, 1), 1)),
                M.metric(ds, M.M_MUSCLE_MASS, round(weight * 0.44 + fitness * 0.005, 1)), M.metric(ds, M.M_BONE_MASS, round(3.4, 1)),
            ) if m]
        if dow == 6:  # weekly BP
            metrics += [m for m in (
                M.metric(ds, M.M_BP_SYS, round(rng.gauss(118, 5))), M.metric(ds, M.M_BP_DIA, round(rng.gauss(76, 4))),
                M.metric(ds, M.M_BP_PULSE, round(rhr + rng.uniform(4, 10))),
            ) if m]

        # --- write the day
        with db.transaction() as conn:
            db.upsert("daily_summaries", [daily], ["date"], conn=conn)
            db.upsert("daily_metrics", metrics, ["date", "metric"], conn=conn)
            db.upsert("intraday_hr", intraday["hr"], ["ts"], conn=conn)
            db.upsert("intraday_stress", intraday["stress"], ["ts"], conn=conn)
            db.upsert("intraday_body_battery", intraday["bb"], ["ts"], conn=conn)
            db.upsert("intraday_respiration", intraday["resp"] + sleep["respiration"], ["ts"], conn=conn)
            db.upsert("intraday_spo2", sleep["spo2"], ["ts"], conn=conn)
            db.upsert("hrv_readings", sleep["hrv"], ["ts"], conn=conn)
            db.upsert("hourly_steps", intraday["hourly_steps"], ["date", "hour"], conn=conn)
            db.upsert("sleep_sessions", [sleep["session"]], ["date"], conn=conn)
            db.upsert("sleep_stages", sleep["stages"], ["date", "start_ts"], conn=conn)
            db.upsert("sleep_movement", sleep["movement"], ["ts"], conn=conn)
            if day_acts:
                db.upsert("activities", day_acts, ["activity_id"], conn=conn)
                for a_id, pts in telemetry.items():
                    db.upsert("activity_telemetry_points", pts, ["activity_id", "elapsed_s"], conn=conn)
                for a_id, lp in laps.items():
                    db.upsert("activity_laps", lp, ["activity_id", "lap_index"], conn=conn)
                for a_id, st in sets.items():
                    db.upsert("strength_sets", st, ["activity_id", "set_index"], conn=conn)
        if (i + 1) % 30 == 0 or i == days - 1:
            print(f"  seeded {i + 1}/{days} days")

    with db.transaction() as conn:
        for domain in ("daily", "intraday", "sleep", "scores", "activities"):
            conn.execute(
                "INSERT OR REPLACE INTO sync_metadata (metric_domain, last_synced_date, last_synced_timestamp, status, message) VALUES (?,?,?,?,?)",
                (domain, iso_date(today), now_iso(), "ok", "Demo data"),
            )
        conn.execute(
            "INSERT INTO sync_runs (mode, start_date, end_date, started_at, finished_at, status, days_total, days_done, message) VALUES (?,?,?,?,?,?,?,?,?)",
            ("demo", iso_date(start), iso_date(today), now_iso(), now_iso(), "ok", days, days, "Seeded demo data"),
        )
    db.set_state("demo_mode", "1")


# ------------------------------------------------------------------ pieces
def _weekly_plan() -> dict[int, list[dict[str, Any]]]:
    return {
        0: [{"category": "strength", "hour": 7}],
        1: [{"category": "running", "hour": 6}],
        2: [{"category": "cycling", "hour": 17}, {"category": "yoga", "hour": 20}],
        3: [{"category": "running", "hour": 6}],
        4: [{"category": "strength", "hour": 7}, {"category": "swimming", "hour": 12}],
        5: [{"category": "running", "hour": 8}],
        6: [{"category": "cycling", "hour": 9}, {"category": "yoga", "hour": 18}],
    }


def _stress_buckets(daily: dict[str, Any], vals: list[int]) -> None:
    step = 180
    rest = sum(1 for v in vals if v < 25) * step
    low = sum(1 for v in vals if 25 <= v < 50) * step
    med = sum(1 for v in vals if 50 <= v < 75) * step
    high = sum(1 for v in vals if v >= 75) * step
    daily.update({"rest_stress_s": rest, "low_stress_s": low, "medium_stress_s": med, "high_stress_s": high,
                  "stress_duration_s": low + med + high})


def _make_sleep(ds: str, start: datetime, end: datetime, rng: random.Random) -> dict[str, Any]:
    total = int((end - start).total_seconds())
    stages: list[dict[str, Any]] = []
    movement: list[dict[str, Any]] = []
    spo2: list[dict[str, Any]] = []
    resp: list[dict[str, Any]] = []
    hrv: list[dict[str, Any]] = []
    t = start
    deep = light = rem = awake = 0
    cycle = 0
    while t < end:
        frac = (t - start).total_seconds() / total
        # Early night favours deep; later favours REM.
        weights = [max(0.04, 0.3 - frac * 0.35), 0.5, 0.05 + frac * 0.35, 0.06]
        stage = rng.choices([0, 1, 2, 3], weights=weights)[0]
        dur = rng.randint(8, 45) * 60 if stage != 3 else rng.randint(2, 9) * 60
        seg_end = min(t + timedelta(seconds=dur), end)
        secs = int((seg_end - t).total_seconds())
        stages.append({"date": ds, "start_ts": to_epoch_ms(t), "end_ts": to_epoch_ms(seg_end), "stage": stage})
        if stage == 0:
            deep += secs
        elif stage == 1:
            light += secs
        elif stage == 2:
            rem += secs
        else:
            awake += secs
        t = seg_end
        cycle += 1
    # overnight vitals every 5 minutes
    t = start
    while t <= end:
        ms = to_epoch_ms(t)
        movement.append({"ts": ms, "date": ds, "level": round(max(0, rng.gauss(1.2, 0.9)), 2)})
        spo2.append({"ts": ms, "date": ds, "spo2": round(min(99, rng.gauss(95.8, 1.1)), 0)})
        resp.append({"ts": ms, "date": ds, "brpm": round(rng.gauss(14.2, 1.1), 1)})
        hrv.append({"ts": ms, "date": ds, "hrv": round(max(15, rng.gauss(55, 14)), 0)})
        t += timedelta(minutes=5)
    sleep_s = total - awake
    score = int(min(100, max(30, 30 + (sleep_s / 3600) * 6 + (deep / max(1, sleep_s)) * 45 - awake / 240 + rng.uniform(-7, 7))))
    session = {
        "date": ds, "sleep_start_ts": to_epoch_ms(start), "sleep_end_ts": to_epoch_ms(end),
        "total_sleep_s": sleep_s, "deep_s": deep, "light_s": light, "rem_s": rem, "awake_s": awake, "unmeasurable_s": 0,
        "sleep_score": score, "score_qualifier": "EXCELLENT" if score >= 90 else "GOOD" if score >= 80 else "FAIR" if score >= 60 else "POOR",
        "avg_spo2": round(sum(s["spo2"] for s in spo2) / len(spo2), 1), "lowest_spo2": min(s["spo2"] for s in spo2),
        "highest_spo2": max(s["spo2"] for s in spo2),
        "avg_respiration": round(sum(r["brpm"] for r in resp) / len(resp), 1), "lowest_respiration": min(r["brpm"] for r in resp),
        "highest_respiration": max(r["brpm"] for r in resp),
        "avg_hrv": round(sum(h["hrv"] for h in hrv) / len(hrv), 0), "resting_hr": None,
        "avg_stress": round(rng.uniform(12, 30), 0), "restless_moments": rng.randint(8, 40),
        "awake_count": sum(1 for s in stages if s["stage"] == 3), "body_battery_change": rng.randint(35, 75),
        "skin_temp_dev_c": round(rng.gauss(0, 0.35), 2), "skin_temp_dev_f": None,
        "avg_movement": round(sum(m["level"] for m in movement) / len(movement), 2), "updated_at": now_iso(),
    }
    session["skin_temp_dev_f"] = round(session["skin_temp_dev_c"] * 1.8, 2)
    return {"session": session, "stages": stages, "movement": movement, "spo2": spo2, "respiration": resp, "hrv": hrv}


def _make_intraday(ds: str, d: date, sleep_start: datetime, sleep_end: datetime, acts: list[dict[str, Any]],
                   rng: random.Random) -> dict[str, Any]:
    day_start = _local_dt(d, 0)
    day_end = _local_dt(d, 24)
    hr: list[dict[str, Any]] = []
    stress: list[dict[str, Any]] = []
    bb: list[dict[str, Any]] = []
    resp: list[dict[str, Any]] = []
    hourly = {h: 0 for h in range(24)}
    windows = [(a["start_ts"], a["start_ts"] + int((a["duration_s"] or 0) * 1000), a) for a in acts]
    level = 35.0
    bb_wake = None
    charged = drained = 0.0
    t = day_start
    hr_base = 60
    while t < day_end:
        ms = to_epoch_ms(t)
        local_h = (t + timedelta(hours=TZ_OFFSET_H)).hour
        asleep = sleep_start <= t < sleep_end
        in_act = next((a for s, e, a in windows if s <= ms < e), None)
        if in_act:
            intensity = {"running": 0.82, "cycling": 0.72, "swimming": 0.7, "strength": 0.55, "yoga": 0.3}.get(in_act["sport_category"], 0.5)
            h = hr_base + intensity * 120 + rng.gauss(0, 6)
            s = -1  # Garmin reports unmeasurable stress during activity
            level -= 0.9 * intensity
            drained += 0.9 * intensity
            steps = int(rng.uniform(150, 340)) if in_act["sport_category"] in ("running", "walking", "hiking") else int(rng.uniform(0, 20))
        elif asleep:
            h = hr_base - 8 + rng.gauss(0, 2.5)
            s = max(0, int(rng.gauss(14, 6)))
            level = min(100, level + 0.37)
            charged += 0.37
            steps = 0
        else:
            diurnal = 1 if 9 <= local_h <= 18 else 0
            h = hr_base + 12 + diurnal * 8 + rng.gauss(0, 7)
            s = max(0, min(100, int(rng.gauss(32 + diurnal * 12, 14))))
            delta = -0.12 - (s / 100) * 0.18 + (0.08 if s < 20 else 0)
            level = max(5, level + delta)
            if delta < 0:
                drained += -delta
            else:
                charged += delta
            steps = int(max(0, rng.gauss(90 if diurnal else 20, 60)))
        if bb_wake is None and t >= sleep_end:
            bb_wake = int(level)
        hr.append({"ts": ms, "date": ds, "hr": int(max(38, h))})
        stress.append({"ts": ms, "date": ds, "stress": s})
        bb.append({"ts": ms, "date": ds, "level": int(level), "status": "charging" if asleep else "draining"})
        if t.minute % 15 == 0:
            resp.append({"ts": ms, "date": ds, "brpm": round(rng.gauss(13 if asleep else 16, 1.2), 1)})
        hourly[local_h] += steps
        t += timedelta(minutes=3)
    levels = [b["level"] for b in bb]
    return {
        "hr": hr, "stress": stress, "bb": bb, "resp": resp,
        "hourly_steps": [{"date": ds, "hour": h, "steps": s} for h, s in hourly.items()],
        "bb_charged": int(charged), "bb_drained": int(drained), "bb_high": max(levels), "bb_low": min(levels),
        "bb_wake": bb_wake or levels[0], "bb_last": levels[-1],
    }


EXERCISES = [
    ("BENCH_PRESS", "BARBELL_BENCH_PRESS", 60, 8), ("SQUAT", "BARBELL_BACK_SQUAT", 90, 6), ("DEADLIFT", "BARBELL_DEADLIFT", 110, 5),
    ("SHOULDER_PRESS", "OVERHEAD_BARBELL_PRESS", 40, 8), ("ROW", "BARBELL_ROW", 60, 10), ("PULL_UP", "PULL_UP", 0, 8),
    ("CURL", "DUMBBELL_BICEPS_CURL", 14, 12), ("LUNGE", "DUMBBELL_LUNGE", 20, 12),
]


def _make_activity(aid: int, ds: str, start: datetime, category: str, fitness: float, rng: random.Random,
                   strength_cycle: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    names = {"running": ["Morning Run", "Tempo Run", "Easy Run", "Long Run", "Trail Run"],
             "cycling": ["Evening Ride", "Hill Repeats", "Endurance Ride", "Gravel Loop"],
             "swimming": ["Pool Swim", "Lunch Swim"], "strength": ["Upper Body", "Lower Body", "Full Body Strength", "Push/Pull"],
             "yoga": ["Evening Yoga", "Mobility Flow", "Yin Yoga"]}
    type_keys = {"running": "running", "cycling": "cycling", "swimming": "lap_swimming", "strength": "strength_training", "yoga": "yoga"}
    duration = {"running": rng.uniform(30, 75), "cycling": rng.uniform(45, 120), "swimming": rng.uniform(30, 50),
                "strength": rng.uniform(40, 65), "yoga": rng.uniform(25, 50)}[category] * 60
    pace_mps = {"running": 3.1 + fitness * 0.004 + rng.uniform(-0.3, 0.3), "cycling": 7.5 + rng.uniform(-1, 1.5),
                "swimming": 0.95 + rng.uniform(-0.1, 0.1)}.get(category)
    distance = pace_mps * duration if pace_mps else None
    pts: list[dict[str, Any]] = []
    laps: list[dict[str, Any]] = []
    sets: list[dict[str, Any]] = []
    gain = None
    avg_hr = {"running": 152, "cycling": 138, "swimming": 135, "strength": 118, "yoga": 82}[category] + rng.uniform(-6, 6)
    max_hr = avg_hr + rng.uniform(15, 30)
    avg_power = 215 + fitness * 0.4 + rng.uniform(-20, 20) if category == "cycling" else (None)
    cadence = {"running": 172 + rng.uniform(-6, 6), "cycling": 86 + rng.uniform(-6, 6)}.get(category)

    if category in ("running", "cycling"):
        pts, laps, gain = _make_track(aid, start, duration, pace_mps, avg_hr, cadence, avg_power, category, rng)
    elif category == "swimming":
        pts = _make_indoor_track(aid, start, duration, avg_hr, rng, pace=pace_mps)
    elif category == "strength":
        sets = _make_sets(aid, start, duration, fitness, rng, strength_cycle)
        pts = _make_indoor_track(aid, start, duration, avg_hr, rng)
    else:
        pts = _make_indoor_track(aid, start, duration, avg_hr, rng)

    zones = _hr_zones(duration, avg_hr, rng)
    kcal = {"running": 11.5, "cycling": 9.0, "swimming": 9.5, "strength": 6.0, "yoga": 3.2}[category] * duration / 60
    act = {
        "activity_id": aid, "date": ds, "start_ts": to_epoch_ms(start),
        "start_local": (start + timedelta(hours=TZ_OFFSET_H)).strftime("%Y-%m-%d %H:%M:%S"),
        "name": rng.choice(names[category]), "description": None, "sport_type": type_keys[category], "sport_category": category,
        "duration_s": round(duration), "elapsed_s": round(duration * rng.uniform(1.0, 1.06)), "moving_s": round(duration * 0.98),
        "distance_m": round(distance) if distance else None, "avg_speed_mps": pace_mps, "max_speed_mps": pace_mps * 1.3 if pace_mps else None,
        "calories": round(kcal), "bmr_calories": round(duration / 60 * 1.25), "avg_hr": int(avg_hr), "max_hr": int(max_hr),
        "elevation_gain_m": gain, "elevation_loss_m": gain, "avg_cadence": cadence, "max_cadence": cadence * 1.1 if cadence else None,
        "avg_power": avg_power, "max_power": avg_power * 2.4 if avg_power else None, "normalized_power": avg_power * 1.08 if avg_power else None,
        "aerobic_te": round(rng.uniform(1.5, 4.5), 1), "anaerobic_te": round(rng.uniform(0, 2.5), 1),
        "training_load": round(duration / 60 * {"running": 2.6, "cycling": 1.8, "swimming": 2.0, "strength": 1.2, "yoga": 0.3}[category]),
        "vo2max": round(49.5 + fitness * 0.08, 1) if category == "running" else None,
        "moderate_min": int(duration / 60 * 0.3), "vigorous_min": int(duration / 60 * 0.6) if category != "yoga" else 0,
        "steps": int(duration / 60 * 170) if category == "running" else None, "lap_count": len(laps) or None,
        **zones,
        "has_polyline": 1 if category in ("running", "cycling") else 0, "fit_status": "parsed", "fit_parsed_at": now_iso(),
        "location_name": "Boulder" if category in ("running", "cycling") else None, "device_id": 3442318, "raw_json": None,
        "updated_at": now_iso(),
    }
    return act, pts, laps, sets


def _hr_zones(duration: float, avg_hr: float, rng: random.Random) -> dict[str, Any]:
    if avg_hr > 145:
        w = [0.08, 0.22, 0.38, 0.24, 0.08]
    elif avg_hr > 125:
        w = [0.18, 0.4, 0.3, 0.1, 0.02]
    else:
        w = [0.55, 0.3, 0.12, 0.03, 0.0]
    w = [max(0, x + rng.uniform(-0.03, 0.03)) for x in w]
    s = sum(w)
    out = {f"hr_zone_{i + 1}_s": round(duration * w[i] / s) for i in range(5)}
    for i, low in enumerate([98, 118, 137, 157, 176]):
        out[f"hr_zone_low_{i + 1}"] = low
    return out


def _make_track(aid: int, start: datetime, duration: float, speed: float, avg_hr: float, cadence: float | None,
                avg_power: float | None, category: str, rng: random.Random):
    pts = []
    n = int(duration)
    step = max(1, n // 1500)  # ~1500 points
    lat0, lon0 = CENTER[0] + rng.uniform(-0.03, 0.03), CENTER[1] + rng.uniform(-0.03, 0.03)
    radius_m = speed * duration / (2 * math.pi) * rng.uniform(0.85, 1.1)
    heading = rng.uniform(0, 2 * math.pi)
    dist = 0.0
    alt_base = 1650 + rng.uniform(-30, 30)
    hr = avg_hr - 25
    prev_alt = alt_base
    gain = 0.0
    laps = []
    lap_start_d = 0.0
    lap_start_t = 0
    lap_hr: list[float] = []
    for t in range(0, n + 1, step):
        frac = t / n
        theta = heading + frac * 2 * math.pi
        wobble = math.sin(frac * 12 * math.pi) * 0.12 + math.sin(frac * 5 * math.pi) * 0.08
        r = radius_m * (1 + wobble)
        lat = lat0 + (r * math.cos(theta)) / 111_320
        lon = lon0 + (r * math.sin(theta)) / (111_320 * math.cos(math.radians(lat0)))
        alt = alt_base + 45 * math.sin(frac * 2 * math.pi) + 18 * math.sin(frac * 7 * math.pi + 1)
        if alt > prev_alt:
            gain += alt - prev_alt
        grade = (alt - prev_alt) / max(1e-6, speed * step)
        prev_alt = alt
        spd = max(0.4, speed * (1 - grade * 6) * (1 + rng.gauss(0, 0.04)) * (0.92 if frac < 0.05 else 1))
        dist += spd * step
        target_hr = avg_hr + grade * 400 + (spd - speed) * 12 + (10 if frac > 0.85 else 0)
        hr += (target_hr - hr) * 0.08 + rng.gauss(0, 1.2)
        lap_hr.append(hr)
        pts.append({
            "activity_id": aid, "elapsed_s": float(t), "ts": to_epoch_ms(start) + t * 1000, "lat": lat, "lon": lon,
            "altitude_m": round(alt, 1), "distance_m": round(dist, 1), "speed_mps": round(spd, 3), "hr": int(hr),
            "cadence": round(cadence * (1 + rng.gauss(0, 0.02)), 1) if cadence else None,
            "power": round(avg_power * (1 + grade * 8) * (1 + rng.gauss(0, 0.12))) if avg_power else None,
            "temperature_c": round(18 + rng.gauss(0, 0.4), 1),
            "grade_adjusted_speed": round(spd * (1 + grade * 4), 3) if category == "running" else None,
            "vertical_oscillation": None, "stance_time": None, "step_length": None,
        })
        if dist - lap_start_d >= 1000 or t >= n:
            laps.append({"activity_id": aid, "lap_index": len(laps), "start_ts": to_epoch_ms(start) + lap_start_t * 1000,
                         "elapsed_s": t - lap_start_t, "moving_s": t - lap_start_t, "distance_m": round(dist - lap_start_d, 1),
                         "avg_hr": int(sum(lap_hr) / len(lap_hr)), "max_hr": int(max(lap_hr)),
                         "avg_speed_mps": round((dist - lap_start_d) / max(1, t - lap_start_t), 3), "max_speed_mps": None,
                         "avg_power": avg_power, "avg_cadence": cadence, "ascent_m": None, "descent_m": None, "calories": None})
            lap_start_d, lap_start_t, lap_hr = dist, t, []
    return pts, laps, round(gain)


def _make_indoor_track(aid: int, start: datetime, duration: float, avg_hr: float, rng: random.Random, pace: float | None = None):
    pts = []
    n = int(duration)
    step = max(1, n // 600)
    hr = avg_hr - 20
    dist = 0.0
    for t in range(0, n + 1, step):
        frac = t / n
        interval = 1 if (int(frac * 10) % 2 == 0) else -1
        hr += ((avg_hr + interval * 12) - hr) * 0.1 + rng.gauss(0, 1.5)
        if pace:
            dist += pace * step
        pts.append({"activity_id": aid, "elapsed_s": float(t), "ts": to_epoch_ms(start) + t * 1000, "lat": None, "lon": None,
                    "altitude_m": None, "distance_m": round(dist, 1) if pace else None, "speed_mps": round(pace * (1 + rng.gauss(0, 0.05)), 3) if pace else None,
                    "hr": int(hr), "cadence": None, "power": None, "temperature_c": round(24 + rng.gauss(0, 0.3), 1),
                    "grade_adjusted_speed": None, "vertical_oscillation": None, "stance_time": None, "step_length": None})
    return pts


def _make_sets(aid: int, start: datetime, duration: float, fitness: float, rng: random.Random, cycle: int):
    sets = []
    chosen = EXERCISES[(cycle % 2) * 4:(cycle % 2) * 4 + 4] + [rng.choice(EXERCISES)]
    t = 0
    idx = 0
    for cat, name, base_w, base_reps in chosen:
        w = base_w * (1 + fitness * 0.0025) if base_w else 0
        for s in range(rng.randint(3, 4)):
            reps = max(3, base_reps + rng.randint(-2, 2))
            weight = round(w * (1 + s * 0.04) / 2.5) * 2.5 if w else 0
            sets.append({"activity_id": aid, "set_index": idx, "start_ts": to_epoch_ms(start) + t * 1000, "set_type": "ACTIVE",
                         "exercise_category": cat, "exercise_name": name, "reps": reps, "weight_kg": weight, "duration_s": reps * 3.2})
            idx += 1
            t += int(reps * 3.2)
            sets.append({"activity_id": aid, "set_index": idx, "start_ts": to_epoch_ms(start) + t * 1000, "set_type": "REST",
                         "exercise_category": None, "exercise_name": None, "reps": None, "weight_kg": None, "duration_s": 90})
            idx += 1
            t += 90
    return sets


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed FitDash with offline demo data")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--reset", action="store_true", help="Delete existing rows first")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    settings = get_settings()
    db = get_db()
    print(f"Seeding {args.days} days of demo data into {settings.resolved_db_path} …")
    seed(db, args.days, args.reset, random.Random(args.seed))
    print("Done.")


if __name__ == "__main__":
    main()
