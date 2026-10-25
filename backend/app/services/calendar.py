"""Per-day aggregation feeding the 52-week contribution grid and habit matrix.

The endpoint returns one record per calendar day in the window with the raw
ingredients (activities, steps, sleep score). The frontend performs filtering
and intensity-metric selection client-side so toggling pills is instant.
"""

from __future__ import annotations

from typing import Any

from app.db import Database
from app.util.timeutil import iso_date, iter_dates, parse_date


def calendar(db: Database, start: str, end: str, step_goal_default: int) -> dict[str, Any]:
    days: dict[str, dict[str, Any]] = {
        iso_date(d): {"date": iso_date(d), "steps": None, "stepGoal": step_goal_default, "sleepScore": None,
                      "sleepS": None, "activities": []}
        for d in iter_dates(parse_date(start), parse_date(end))
    }
    for r in db.query("SELECT date, total_steps, step_goal FROM daily_summaries WHERE date BETWEEN ? AND ?", (start, end)):
        if r["date"] in days:
            days[r["date"]]["steps"] = r["total_steps"]
            if r["step_goal"]:
                days[r["date"]]["stepGoal"] = r["step_goal"]
    for r in db.query("SELECT date, sleep_score, total_sleep_s FROM sleep_sessions WHERE date BETWEEN ? AND ?", (start, end)):
        if r["date"] in days:
            days[r["date"]]["sleepScore"] = r["sleep_score"]
            days[r["date"]]["sleepS"] = r["total_sleep_s"]
    acts = db.query(
        """SELECT activity_id, date, name, sport_type, sport_category, duration_s, distance_m, calories, avg_hr,
                  training_load, elevation_gain_m, start_ts
           FROM activities WHERE date BETWEEN ? AND ? ORDER BY start_ts""",
        (start, end),
    )
    for a in acts:
        if a["date"] in days:
            days[a["date"]]["activities"].append({
                "id": a["activity_id"], "name": a["name"], "type": a["sport_type"], "category": a["sport_category"],
                "durationS": a["duration_s"], "distanceM": a["distance_m"], "calories": a["calories"],
                "avgHr": a["avg_hr"], "trainingLoad": a["training_load"], "elevationGainM": a["elevation_gain_m"],
                "startTs": a["start_ts"],
            })
    return {"start": start, "end": end, "days": list(days.values())}
