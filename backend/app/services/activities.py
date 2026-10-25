"""Activity list, deep-dive detail and strength analytics."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.db import Database

LIST_COLUMNS = """activity_id, date, start_ts, start_local, name, sport_type, sport_category, duration_s, elapsed_s,
    moving_s, distance_m, avg_speed_mps, max_speed_mps, calories, avg_hr, max_hr, elevation_gain_m, elevation_loss_m,
    avg_cadence, avg_power, normalized_power, aerobic_te, anaerobic_te, training_load, vo2max, steps, lap_count,
    hr_zone_1_s, hr_zone_2_s, hr_zone_3_s, hr_zone_4_s, hr_zone_5_s, hr_zone_low_1, hr_zone_low_2, hr_zone_low_3,
    hr_zone_low_4, hr_zone_low_5, has_polyline, fit_status, location_name"""


def list_activities(db: Database, start: str, end: str, category: str | None = None, q: str | None = None,
                    limit: int = 500) -> list[dict[str, Any]]:
    where = ["date BETWEEN ? AND ?"]
    params: list[Any] = [start, end]
    if category and category != "all":
        where.append("sport_category = ?")
        params.append(category)
    if q:
        where.append("(LOWER(name) LIKE ? OR LOWER(sport_type) LIKE ? OR LOWER(location_name) LIKE ?)")
        like = f"%{q.lower()}%"
        params += [like, like, like]
    params.append(limit)
    rows = db.query(f"SELECT {LIST_COLUMNS} FROM activities WHERE {' AND '.join(where)} ORDER BY start_ts DESC LIMIT ?", params)
    return [_shape(r) for r in rows]


def _shape(r: dict[str, Any]) -> dict[str, Any]:
    zones = [r.get(f"hr_zone_{i}_s") for i in range(1, 6)]
    bounds = [r.get(f"hr_zone_low_{i}") for i in range(1, 6)]
    return {
        "id": r["activity_id"], "date": r["date"], "startTs": r["start_ts"], "startLocal": r["start_local"],
        "name": r["name"], "type": r["sport_type"], "category": r["sport_category"],
        "durationS": r["duration_s"], "elapsedS": r["elapsed_s"], "movingS": r["moving_s"],
        "distanceM": r["distance_m"], "avgSpeedMps": r["avg_speed_mps"], "maxSpeedMps": r["max_speed_mps"],
        "calories": r["calories"], "avgHr": r["avg_hr"], "maxHr": r["max_hr"],
        "elevationGainM": r["elevation_gain_m"], "elevationLossM": r["elevation_loss_m"],
        "avgCadence": r["avg_cadence"], "avgPower": r["avg_power"], "normalizedPower": r["normalized_power"],
        "aerobicTe": r["aerobic_te"], "anaerobicTe": r["anaerobic_te"], "trainingLoad": r["training_load"],
        "vo2max": r["vo2max"], "steps": r["steps"], "lapCount": r["lap_count"],
        "hrZones": {"secondsInZone": zones, "lowBoundaries": bounds},
        "hasPolyline": bool(r["has_polyline"]), "fitStatus": r["fit_status"], "location": r["location_name"],
    }


def activity_detail(db: Database, activity_id: int) -> dict[str, Any] | None:
    row = db.query_one(f"SELECT {LIST_COLUMNS} FROM activities WHERE activity_id = ?", (activity_id,))
    if not row:
        return None
    summary = _shape(row)
    points = db.query(
        """SELECT elapsed_s, ts, lat, lon, altitude_m, distance_m, speed_mps, hr, cadence, power, temperature_c,
                  grade_adjusted_speed FROM activity_telemetry_points WHERE activity_id = ? ORDER BY elapsed_s""",
        (activity_id,),
    )
    laps = db.query("SELECT * FROM activity_laps WHERE activity_id = ? ORDER BY lap_index", (activity_id,))
    sets = db.query("SELECT * FROM strength_sets WHERE activity_id = ? ORDER BY set_index", (activity_id,))
    detail: dict[str, Any] = {
        "summary": summary,
        "telemetry": {
            "elapsedS": [p["elapsed_s"] for p in points],
            "ts": [p["ts"] for p in points],
            "lat": [p["lat"] for p in points],
            "lon": [p["lon"] for p in points],
            "altitudeM": [p["altitude_m"] for p in points],
            "distanceM": [p["distance_m"] for p in points],
            "speedMps": [p["speed_mps"] for p in points],
            "hr": [p["hr"] for p in points],
            "cadence": [p["cadence"] for p in points],
            "power": [p["power"] for p in points],
            "temperatureC": [p["temperature_c"] for p in points],
            "gradeAdjustedSpeedMps": [p["grade_adjusted_speed"] for p in points],
        },
        "laps": [{
            "index": l["lap_index"], "startTs": l["start_ts"], "elapsedS": l["elapsed_s"], "movingS": l["moving_s"],
            "distanceM": l["distance_m"], "avgHr": l["avg_hr"], "maxHr": l["max_hr"], "avgSpeedMps": l["avg_speed_mps"],
            "maxSpeedMps": l["max_speed_mps"], "avgPower": l["avg_power"], "avgCadence": l["avg_cadence"],
            "ascentM": l["ascent_m"], "descentM": l["descent_m"], "calories": l["calories"],
        } for l in laps],
        "strength": None,
    }
    if summary["category"] == "strength" or sets:
        detail["strength"] = strength_summary(db, activity_id, sets)
    return detail


def _exercise_label(s: dict[str, Any]) -> str:
    name = (s.get("exercise_name") or "").replace("_", " ").title()
    cat = (s.get("exercise_category") or "Unknown").replace("_", " ").title()
    return f"{cat} · {name}" if name else cat


def epley_1rm(weight_kg: float | None, reps: int | None) -> float | None:
    if not weight_kg or not reps:
        return None
    if reps == 1:
        return weight_kg
    return round(weight_kg * (1 + reps / 30.0), 2)


def strength_summary(db: Database, activity_id: int, sets: list[dict[str, Any]]) -> dict[str, Any]:
    active = [s for s in sets if (s.get("set_type") or "ACTIVE").upper() != "REST"]
    per_exercise: dict[str, dict[str, Any]] = {}
    for s in active:
        label = _exercise_label(s)
        agg = per_exercise.setdefault(label, {"exercise": label, "category": s.get("exercise_category"),
                                              "name": s.get("exercise_name"), "sets": 0, "reps": 0, "volumeKg": 0.0,
                                              "maxWeightKg": 0.0, "best1rm": None})
        reps = s.get("reps") or 0
        w = s.get("weight_kg") or 0.0
        agg["sets"] += 1
        agg["reps"] += reps
        agg["volumeKg"] += reps * w
        agg["maxWeightKg"] = max(agg["maxWeightKg"], w)
        e = epley_1rm(w, reps)
        if e and (agg["best1rm"] is None or e > agg["best1rm"]):
            agg["best1rm"] = e

    # per-muscle-group (category) volume
    per_category: dict[str, float] = defaultdict(float)
    for s in active:
        per_category[(s.get("exercise_category") or "UNKNOWN")] += (s.get("reps") or 0) * (s.get("weight_kg") or 0.0)

    # e1RM progression for each exercise in this workout across all history
    progression: dict[str, list[list[Any]]] = {}
    keys = {(s.get("exercise_category"), s.get("exercise_name")) for s in active}
    for cat, name in keys:
        hist = db.query(
            """SELECT a.date, MAX(s.weight_kg * (1 + s.reps / 30.0)) AS e1rm, MAX(s.weight_kg) AS top
               FROM strength_sets s JOIN activities a ON a.activity_id = s.activity_id
               WHERE COALESCE(s.exercise_category,'') = COALESCE(?, '') AND COALESCE(s.exercise_name,'') = COALESCE(?, '')
                 AND COALESCE(s.set_type,'ACTIVE') <> 'REST' AND s.weight_kg > 0 AND s.reps > 0
               GROUP BY a.date ORDER BY a.date""",
            (cat, name),
        )
        label = _exercise_label({"exercise_category": cat, "exercise_name": name})
        progression[label] = [[h["date"], round(h["e1rm"], 1), h["top"]] for h in hist]

    return {
        "sets": [{
            "index": s["set_index"], "startTs": s["start_ts"], "type": s["set_type"], "exercise": _exercise_label(s),
            "category": s["exercise_category"], "name": s["exercise_name"], "reps": s["reps"],
            "weightKg": s["weight_kg"], "durationS": s["duration_s"], "e1rm": epley_1rm(s["weight_kg"], s["reps"]),
        } for s in sets],
        "perExercise": sorted(per_exercise.values(), key=lambda x: -x["volumeKg"]),
        "perCategory": [{"category": k, "volumeKg": round(v, 1)} for k, v in sorted(per_category.items(), key=lambda kv: -kv[1])],
        "totalVolumeKg": round(sum(per_category.values()), 1),
        "totalSets": len(active),
        "totalReps": sum(s.get("reps") or 0 for s in active),
        "progression": progression,
    }


def categories_summary(db: Database, start: str, end: str) -> list[dict[str, Any]]:
    return db.query(
        """SELECT sport_category AS category, COUNT(*) AS count, SUM(duration_s) AS duration_s, SUM(distance_m) AS distance_m,
                  SUM(calories) AS calories FROM activities WHERE date BETWEEN ? AND ? GROUP BY sport_category ORDER BY count DESC""",
        (start, end),
    )
