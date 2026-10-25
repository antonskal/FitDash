"""Parse Garmin `.fit` activity files into telemetry points, laps and strength sets.

Garmin's "ORIGINAL" download is a zip archive containing one `.fit` file.
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fitparse import FitFile, FitParseError

from app.util.timeutil import to_epoch_ms

log = logging.getLogger(__name__)

SEMICIRCLE_TO_DEG = 180.0 / 2**31


class FitUnavailable(Exception):
    """The archive did not contain a parseable FIT file."""


@dataclass
class ParsedFit:
    start_ts: int
    points: list[dict[str, Any]] = field(default_factory=list)
    laps: list[dict[str, Any]] = field(default_factory=list)
    sets: list[dict[str, Any]] = field(default_factory=list)
    session: dict[str, Any] = field(default_factory=dict)
    raw_fit: bytes | None = None


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract_fit_bytes(archive: bytes) -> bytes:
    """Return the FIT payload from a Garmin ORIGINAL download (zip or bare FIT)."""
    if archive[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith(".fit")), None)
            if not name:
                raise FitUnavailable("No .fit file inside downloaded archive")
            return zf.read(name)
    if len(archive) > 12 and archive[8:12] == b".FIT":
        return archive
    raise FitUnavailable("Downloaded payload is neither a zip nor a FIT file")


def parse_fit(fit_bytes: bytes, activity_id: int, max_points: int = 6000) -> ParsedFit:
    try:
        fit = FitFile(io.BytesIO(fit_bytes))
        fit.parse()
    except (FitParseError, Exception) as exc:  # fitparse raises assorted errors on corrupt files
        raise FitUnavailable(f"FIT parse failed: {exc}") from exc

    records = [m.get_values() for m in fit.get_messages("record")]
    records = [r for r in records if r.get("timestamp")]
    if not records:
        raise FitUnavailable("FIT file contains no record messages")

    start_dt = _utc(records[0]["timestamp"])
    assert start_dt is not None
    start_ts = to_epoch_ms(start_dt)

    points: list[dict[str, Any]] = []
    seen_elapsed: set[float] = set()
    for r in records:
        ts_dt = _utc(r["timestamp"])
        assert ts_dt is not None
        elapsed = round((ts_dt - start_dt).total_seconds(), 3)
        if elapsed in seen_elapsed:
            continue
        seen_elapsed.add(elapsed)
        lat = r.get("position_lat")
        lon = r.get("position_long")
        speed = r.get("enhanced_speed", None)
        if speed is None:
            speed = r.get("speed")
        alt = r.get("enhanced_altitude", None)
        if alt is None:
            alt = r.get("altitude")
        cadence = _f(r.get("cadence"))
        frac = _f(r.get("fractional_cadence"))
        if cadence is not None and frac:
            cadence += frac
        gas = r.get("unknown_140")  # Garmin grade-adjusted speed (mm/s)
        points.append({
            "activity_id": activity_id,
            "elapsed_s": elapsed,
            "ts": to_epoch_ms(ts_dt),
            "lat": int(lat) * SEMICIRCLE_TO_DEG if lat is not None else None,
            "lon": int(lon) * SEMICIRCLE_TO_DEG if lon is not None else None,
            "altitude_m": _f(alt),
            "distance_m": _f(r.get("distance")),
            "speed_mps": _f(speed),
            "hr": int(r["heart_rate"]) if r.get("heart_rate") is not None else None,
            "cadence": cadence,
            "power": _f(r.get("power")),
            "temperature_c": _f(r.get("temperature")),
            "grade_adjusted_speed": (_f(gas) or 0) / 1000.0 if gas else None,
            "vertical_oscillation": _f(r.get("vertical_oscillation")),
            "stance_time": _f(r.get("stance_time")),
            "step_length": _f(r.get("step_length")),
        })

    if len(points) > max_points:
        points = _downsample(points, max_points)

    laps: list[dict[str, Any]] = []
    for idx, lap in enumerate(m.get_values() for m in fit.get_messages("lap")):
        start = _utc(lap.get("start_time") or lap.get("timestamp"))
        avg_speed = lap.get("enhanced_avg_speed", None)
        if avg_speed is None:
            avg_speed = lap.get("avg_speed")
        max_speed = lap.get("enhanced_max_speed", None)
        if max_speed is None:
            max_speed = lap.get("max_speed")
        laps.append({
            "activity_id": activity_id,
            "lap_index": idx,
            "start_ts": to_epoch_ms(start) if start else None,
            "elapsed_s": _f(lap.get("total_elapsed_time")),
            "moving_s": _f(lap.get("total_moving_time") or lap.get("total_timer_time")),
            "distance_m": _f(lap.get("total_distance")),
            "avg_hr": int(lap["avg_heart_rate"]) if lap.get("avg_heart_rate") is not None else None,
            "max_hr": int(lap["max_heart_rate"]) if lap.get("max_heart_rate") is not None else None,
            "avg_speed_mps": _f(avg_speed),
            "max_speed_mps": _f(max_speed),
            "avg_power": _f(lap.get("avg_power")),
            "avg_cadence": _f(lap.get("avg_cadence")),
            "ascent_m": _f(lap.get("total_ascent")),
            "descent_m": _f(lap.get("total_descent")),
            "calories": _f(lap.get("total_calories")),
        })

    sets: list[dict[str, Any]] = []
    for idx, s in enumerate(m.get_values() for m in fit.get_messages("set")):
        set_type = s.get("set_type")
        start = _utc(s.get("start_time") or s.get("timestamp"))
        category = s.get("category")
        if isinstance(category, (list, tuple)):
            category = next((c for c in category if c is not None), None)
        weight = _f(s.get("weight"))
        sets.append({
            "activity_id": activity_id,
            "set_index": idx,
            "start_ts": to_epoch_ms(start) if start else None,
            "set_type": str(set_type).upper() if set_type is not None else None,
            "exercise_category": str(category).upper() if category is not None else None,
            "exercise_name": None,  # FIT only carries numeric sub-category codes; API has names
            "reps": int(s["repetitions"]) if s.get("repetitions") is not None else None,
            "weight_kg": weight,
            "duration_s": _f(s.get("duration")),
        })

    session: dict[str, Any] = {}
    for sess in (m.get_values() for m in fit.get_messages("session")):
        session = {
            "sport": str(sess.get("sport")) if sess.get("sport") is not None else None,
            "sub_sport": str(sess.get("sub_sport")) if sess.get("sub_sport") is not None else None,
            "total_training_effect": _f(sess.get("total_training_effect")),
            "total_anaerobic_training_effect": _f(sess.get("total_anaerobic_training_effect")),
            "normalized_power": _f(sess.get("normalized_power")),
            "avg_temperature": _f(sess.get("avg_temperature")),
            "total_ascent": _f(sess.get("total_ascent")),
            "total_descent": _f(sess.get("total_descent")),
        }
        break

    return ParsedFit(start_ts=start_ts, points=points, laps=laps, sets=sets, session=session, raw_fit=fit_bytes)


def _downsample(points: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    """Uniform stride downsample that always keeps first and last points."""
    if len(points) <= target:
        return points
    stride = len(points) / target
    out = [points[int(i * stride)] for i in range(target)]
    if out[-1] is not points[-1]:
        out.append(points[-1])
    return out
