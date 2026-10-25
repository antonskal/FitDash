"""Pure functions mapping raw Garmin Connect JSON → database rows.

Each mapper is defensive: Garmin omits keys freely and occasionally changes
list/dict shapes between API versions, so everything uses `.get` and
tolerates `None`.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from app.garmin.sports import categorize
from app.util.timeutil import local_offset_ms, now_iso, parse_gmt_ms, parse_naive

# daily_metrics keys ---------------------------------------------------------
M_VO2MAX_RUN = "vo2max_running"
M_VO2MAX_CYCLE = "vo2max_cycling"
M_FITNESS_AGE = "fitness_age"
M_TRAINING_READINESS = "training_readiness"
M_TRAINING_READINESS_LEVEL = "training_readiness_level"
M_RECOVERY_TIME_H = "recovery_time_h"
M_HRV_LAST_NIGHT = "hrv_last_night"
M_HRV_WEEKLY_AVG = "hrv_weekly_avg"
M_HRV_STATUS = "hrv_status"
M_HRV_BASELINE_LOW = "hrv_baseline_low"
M_HRV_BASELINE_HIGH = "hrv_baseline_high"
M_ENDURANCE = "endurance_score"
M_HILL = "hill_score"
M_HILL_STRENGTH = "hill_strength"
M_HILL_ENDURANCE = "hill_endurance"
M_LT_HR = "lactate_threshold_hr"
M_LT_SPEED = "lactate_threshold_speed_mps"
M_RACE_5K = "race_5k_s"
M_RACE_10K = "race_10k_s"
M_RACE_HALF = "race_half_s"
M_RACE_FULL = "race_marathon_s"
M_HYDRATION = "hydration_ml"
M_HYDRATION_GOAL = "hydration_goal_ml"
M_SWEAT_LOSS = "sweat_loss_ml"
M_WEIGHT = "weight_kg"
M_BMI = "bmi"
M_BODY_FAT = "body_fat_pct"
M_BODY_WATER = "body_water_pct"
M_MUSCLE_MASS = "muscle_mass_kg"
M_BONE_MASS = "bone_mass_kg"
M_BP_SYS = "bp_systolic"
M_BP_DIA = "bp_diastolic"
M_BP_PULSE = "bp_pulse"
M_TRAINING_STATUS = "training_status"
M_WEEKLY_LOAD = "weekly_training_load"
M_ACWR = "acwr"
M_RHR_7D = "resting_hr_7d_avg"


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def _int(v: Any) -> int | None:
    f = _num(v)
    return int(round(f)) if f is not None else None


def metric(date: str, name: str, value: Any, text: str | None = None, ts: int | None = None) -> dict[str, Any] | None:
    num = _num(value)
    if num is None and text is None:
        return None
    return {"date": date, "metric": name, "value": num, "text_value": text, "source_ts": ts}


# ---------------------------------------------------------------- daily stats
def map_daily_summary(date: str, stats: dict[str, Any]) -> dict[str, Any] | None:
    if not stats:
        return None
    return {
        "date": date,
        "wellness_start_ts": parse_gmt_ms(stats.get("wellnessStartTimeGmt")),
        "wellness_end_ts": parse_gmt_ms(stats.get("wellnessEndTimeGmt")),
        "total_steps": _int(stats.get("totalSteps")),
        "step_goal": _int(stats.get("dailyStepGoal")),
        "total_distance_m": _num(stats.get("totalDistanceMeters")),
        "active_kcal": _num(stats.get("activeKilocalories")),
        "bmr_kcal": _num(stats.get("bmrKilocalories")),
        "total_kcal": _num(stats.get("totalKilocalories")),
        "moderate_intensity_min": _int(stats.get("moderateIntensityMinutes")),
        "vigorous_intensity_min": _int(stats.get("vigorousIntensityMinutes")),
        "intensity_goal_min": _int(stats.get("intensityMinutesGoal")),
        "floors_ascended": _num(stats.get("floorsAscended")),
        "floors_descended": _num(stats.get("floorsDescended")),
        "highly_active_s": _int(stats.get("highlyActiveSeconds")),
        "active_s": _int(stats.get("activeSeconds")),
        "sedentary_s": _int(stats.get("sedentarySeconds")),
        "sleeping_s": _int(stats.get("sleepingSeconds")),
        "resting_hr": _int(stats.get("restingHeartRate")),
        "min_hr": _int(stats.get("minHeartRate")),
        "max_hr": _int(stats.get("maxHeartRate")),
        "avg_stress": _int(stats.get("averageStressLevel")),
        "max_stress": _int(stats.get("maxStressLevel")),
        "stress_duration_s": _int(stats.get("stressDuration")),
        "rest_stress_s": _int(stats.get("restStressDuration")),
        "low_stress_s": _int(stats.get("lowStressDuration")),
        "medium_stress_s": _int(stats.get("mediumStressDuration")),
        "high_stress_s": _int(stats.get("highStressDuration")),
        "body_battery_charged": _int(stats.get("bodyBatteryChargedValue")),
        "body_battery_drained": _int(stats.get("bodyBatteryDrainedValue")),
        "body_battery_highest": _int(stats.get("bodyBatteryHighestValue")),
        "body_battery_lowest": _int(stats.get("bodyBatteryLowestValue")),
        "body_battery_at_wake": _int(stats.get("bodyBatteryAtWakeTime")),
        "body_battery_most_recent": _int(stats.get("bodyBatteryMostRecentValue")),
        "avg_spo2": _num(stats.get("averageSpo2")),
        "lowest_spo2": _num(stats.get("lowestSpo2")),
        "avg_respiration": _num(stats.get("avgWakingRespirationValue")),
        "lowest_respiration": _num(stats.get("lowestRespirationValue")),
        "highest_respiration": _num(stats.get("highestRespirationValue")),
        "avg_skin_temp_dev_c": _num(stats.get("avgSkinTempDeviationC")),
        "avg_skin_temp_dev_f": _num(stats.get("avgSkinTempDeviationF")),
        "updated_at": now_iso(),
    }


def daily_local_offset_ms(stats: dict[str, Any]) -> int | None:
    return local_offset_ms(stats.get("wellnessStartTimeGmt"), stats.get("wellnessStartTimeLocal"))


# ---------------------------------------------------------------- intraday
def map_intraday_hr(date: str, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    for entry in payload.get("heartRateValues") or []:
        if entry and len(entry) >= 2 and entry[1] is not None and entry[0] is not None:
            rows.append({"ts": int(entry[0]), "date": date, "hr": int(entry[1])})
    metrics = []
    m = metric(date, M_RHR_7D, payload.get("lastSevenDaysAvgRestingHeartRate"))
    if m:
        metrics.append(m)
    return rows, metrics


def map_intraday_stress(date: str, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stress = []
    for entry in payload.get("stressValuesArray") or []:
        if entry and len(entry) >= 2 and entry[0] is not None and entry[1] is not None:
            stress.append({"ts": int(entry[0]), "date": date, "stress": int(entry[1])})
    bb = []
    for entry in payload.get("bodyBatteryValuesArray") or []:
        # [timestamp, status, level, version]
        if entry and len(entry) >= 3 and entry[0] is not None and entry[2] is not None:
            bb.append({"ts": int(entry[0]), "date": date, "level": int(entry[2]),
                       "status": str(entry[1]) if entry[1] is not None else None})
    return stress, bb


def map_intraday_respiration(date: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in payload.get("respirationValuesArray") or []:
        if entry and len(entry) >= 2 and entry[0] is not None and entry[1] is not None and float(entry[1]) > 0:
            rows.append({"ts": int(entry[0]), "date": date, "brpm": float(entry[1])})
    return rows


def map_hourly_steps(date: str, buckets: Iterable[dict[str, Any]], offset_ms: int | None) -> list[dict[str, Any]]:
    """Aggregate Garmin's 15-minute step buckets into local hours."""
    hours: dict[int, int] = defaultdict(int)
    for b in buckets or []:
        steps = b.get("steps")
        if steps is None:
            continue
        start_ms = parse_gmt_ms(b.get("startGMT"))
        if start_ms is None:
            continue
        local_ms = start_ms + (offset_ms or 0)
        hour = int((local_ms // 3_600_000) % 24)
        hours[hour] += int(steps)
    return [{"date": date, "hour": h, "steps": s} for h, s in sorted(hours.items())]


def map_hrv(date: str, payload: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not payload:
        return [], []
    readings = []
    for r in payload.get("hrvReadings") or []:
        ts = parse_gmt_ms(r.get("readingTimeGMT"))
        if ts is not None and r.get("hrvValue") is not None:
            readings.append({"ts": ts, "date": date, "hrv": float(r["hrvValue"])})
    summary = payload.get("hrvSummary") or {}
    baseline = summary.get("baseline") or {}
    metrics = [
        m for m in (
            metric(date, M_HRV_LAST_NIGHT, summary.get("lastNightAvg")),
            metric(date, M_HRV_WEEKLY_AVG, summary.get("weeklyAvg")),
            metric(date, M_HRV_STATUS, None, text=summary.get("status")),
            metric(date, M_HRV_BASELINE_LOW, baseline.get("balancedLow")),
            metric(date, M_HRV_BASELINE_HIGH, baseline.get("balancedUpper")),
        ) if m
    ]
    return readings, metrics


# ---------------------------------------------------------------- sleep
STAGE_BY_LEVEL = {0: 0, 1: 1, 2: 2, 3: 3}  # Garmin: 0 deep, 1 light, 2 rem, 3 awake


def map_sleep(date: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Returns {"session": row|None, "stages": [...], "movement": [...], "spo2": [...], "respiration": [...], "hrv": [...]}."""
    out: dict[str, Any] = {"session": None, "stages": [], "movement": [], "spo2": [], "respiration": [], "hrv": []}
    if not payload:
        return out
    dto = payload.get("dailySleepDTO") or {}
    start = dto.get("sleepStartTimestampGMT")
    end = dto.get("sleepEndTimestampGMT")
    if start and end and (dto.get("sleepTimeSeconds") or 0) > 0:
        scores = dto.get("sleepScores") or {}
        overall = scores.get("overall") or {}
        out["session"] = {
            "date": dto.get("calendarDate") or date,
            "sleep_start_ts": parse_gmt_ms(start),
            "sleep_end_ts": parse_gmt_ms(end),
            "total_sleep_s": _int(dto.get("sleepTimeSeconds")),
            "deep_s": _int(dto.get("deepSleepSeconds")),
            "light_s": _int(dto.get("lightSleepSeconds")),
            "rem_s": _int(dto.get("remSleepSeconds")),
            "awake_s": _int(dto.get("awakeSleepSeconds")),
            "unmeasurable_s": _int(dto.get("unmeasurableSleepSeconds")),
            "sleep_score": _int(overall.get("value")),
            "score_qualifier": overall.get("qualifierKey"),
            "avg_spo2": _num(dto.get("averageSpO2Value")),
            "lowest_spo2": _num(dto.get("lowestSpO2Value")),
            "highest_spo2": _num(dto.get("highestSpO2Value")),
            "avg_respiration": _num(dto.get("averageRespirationValue")),
            "lowest_respiration": _num(dto.get("lowestRespirationValue")),
            "highest_respiration": _num(dto.get("highestRespirationValue")),
            "avg_hrv": _num(payload.get("avgOvernightHrv")),
            "resting_hr": _int(payload.get("restingHeartRate")),
            "avg_stress": _num(dto.get("avgSleepStress")),
            "restless_moments": _int(payload.get("restlessMomentsCount")),
            "awake_count": _int(dto.get("awakeCount")),
            "body_battery_change": _int(payload.get("bodyBatteryChange")),
            "skin_temp_dev_c": _num(payload.get("avgSkinTempDeviationC") or dto.get("avgSkinTempDeviationC")),
            "skin_temp_dev_f": _num(payload.get("avgSkinTempDeviationF") or dto.get("avgSkinTempDeviationF")),
            "avg_movement": None,
            "updated_at": now_iso(),
        }
    sleep_date = out["session"]["date"] if out["session"] else date

    for lvl in payload.get("sleepLevels") or []:
        s, e = parse_gmt_ms(lvl.get("startGMT")), parse_gmt_ms(lvl.get("endGMT"))
        level = lvl.get("activityLevel")
        if s is None or e is None or level is None:
            continue
        out["stages"].append({"date": sleep_date, "start_ts": s, "end_ts": e, "stage": STAGE_BY_LEVEL.get(int(level), 3)})

    movement_vals = []
    for mv in payload.get("sleepMovement") or []:
        s = parse_gmt_ms(mv.get("startGMT"))
        lvl = mv.get("activityLevel")
        if s is not None and lvl is not None:
            out["movement"].append({"ts": s, "date": sleep_date, "level": float(lvl)})
            movement_vals.append(float(lvl))
    if out["session"] and movement_vals:
        out["session"]["avg_movement"] = sum(movement_vals) / len(movement_vals)

    for sp in payload.get("wellnessEpochSPO2DataDTOList") or []:
        ts = parse_gmt_ms(sp.get("epochTimestamp"))
        if ts is not None and sp.get("spo2Reading"):
            out["spo2"].append({"ts": ts, "date": sleep_date, "spo2": float(sp["spo2Reading"])})

    for rp in payload.get("wellnessEpochRespirationDataDTOList") or []:
        ts = parse_gmt_ms(rp.get("startTimeGMT"))
        if ts is not None and rp.get("respirationValue"):
            out["respiration"].append({"ts": ts, "date": sleep_date, "brpm": float(rp["respirationValue"])})

    for hv in payload.get("hrvData") or []:
        ts = parse_gmt_ms(hv.get("startGMT"))
        if ts is not None and hv.get("value"):
            out["hrv"].append({"ts": ts, "date": sleep_date, "hrv": float(hv["value"])})
    return out


# ---------------------------------------------------------------- scores
def map_training_readiness(date: str, payload: Any) -> list[dict[str, Any]]:
    items = payload if isinstance(payload, list) else ([payload] if payload else [])
    best = None
    for item in items:
        if not isinstance(item, dict) or item.get("score") is None:
            continue
        if best is None or (item.get("timestamp") or "") > (best.get("timestamp") or ""):
            best = item
    if not best:
        return []
    ts = parse_gmt_ms(best.get("timestamp"))
    return [m for m in (
        metric(date, M_TRAINING_READINESS, best.get("score"), ts=ts),
        metric(date, M_TRAINING_READINESS_LEVEL, None, text=best.get("level"), ts=ts),
        metric(date, M_RECOVERY_TIME_H, best.get("recoveryTime"), ts=ts),
    ) if m]


def map_max_metrics(date: str, payload: Any) -> list[dict[str, Any]]:
    items = payload if isinstance(payload, list) else ([payload] if payload else [])
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        generic = item.get("generic") or {}
        cycling = item.get("cycling") or {}
        for m in (
            metric(date, M_VO2MAX_RUN, generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")),
            metric(date, M_VO2MAX_CYCLE, cycling.get("vo2MaxPreciseValue") or cycling.get("vo2MaxValue")),
        ):
            if m:
                out.append(m)
    return out


def map_fitness_age(date: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    m = metric(date, M_FITNESS_AGE, payload.get("fitnessAge"))
    return [m] if m else []


def map_endurance(date: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    m = metric(date, M_ENDURANCE, payload.get("overallScore"))
    return [m] if m else []


def map_hill(date: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [m for m in (
        metric(date, M_HILL, payload.get("overallScore")),
        metric(date, M_HILL_STRENGTH, payload.get("strengthScore")),
        metric(date, M_HILL_ENDURANCE, payload.get("enduranceScore")),
    ) if m]


def map_training_status(date: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    latest = ((payload.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData")) or {}
    out: list[dict[str, Any]] = []
    for _device, ts in latest.items():
        if not isinstance(ts, dict):
            continue
        acute = ts.get("acuteTrainingLoadDTO") or {}
        for m in (
            metric(date, M_TRAINING_STATUS, None, text=ts.get("trainingStatusFeedbackPhrase") or str(ts.get("trainingStatus"))),
            metric(date, M_WEEKLY_LOAD, ts.get("weeklyTrainingLoad")),
            metric(date, M_ACWR, acute.get("dailyAcuteChronicWorkloadRatio")),
        ):
            if m:
                out.append(m)
        break  # first device only
    return out


def map_hydration(date: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [m for m in (
        metric(date, M_HYDRATION, payload.get("valueInML")),
        metric(date, M_HYDRATION_GOAL, payload.get("goalInML")),
        metric(date, M_SWEAT_LOSS, payload.get("sweatLossInML")),
    ) if m]


def _find_dated_items(payload: Any) -> list[dict[str, Any]]:
    """Locate the list of per-day dicts in a Garmin range response of unknown shape."""
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "calendarDate" in v[0]:
                return v
        if "calendarDate" in payload:
            return [payload]
    return []


def map_race_predictions_range(payload: Any) -> list[dict[str, Any]]:
    out = []
    for item in _find_dated_items(payload):
        d = item.get("calendarDate")
        if not d:
            continue
        for m in (
            metric(d, M_RACE_5K, item.get("time5K")),
            metric(d, M_RACE_10K, item.get("time10K")),
            metric(d, M_RACE_HALF, item.get("timeHalfMarathon")),
            metric(d, M_RACE_FULL, item.get("timeMarathon")),
        ):
            if m:
                out.append(m)
    return out


def map_hill_range(payload: Any) -> list[dict[str, Any]]:
    out = []
    for item in _find_dated_items(payload):
        d = item.get("calendarDate")
        if d:
            out.extend(map_hill(d, item))
    return out


def map_endurance_range(payload: Any) -> list[dict[str, Any]]:
    out = []
    for item in _find_dated_items(payload):
        d = item.get("calendarDate")
        if d:
            out.extend(map_endurance(d, item))
    return out


def map_weigh_ins_range(payload: Any) -> list[dict[str, Any]]:
    out = []
    for day in (payload or {}).get("dailyWeightSummaries") or []:
        d = day.get("summaryDate")
        metrics_list = day.get("allWeightMetrics") or []
        if not d or not metrics_list:
            continue
        # Prefer the latest measurement of the day.
        w = sorted(metrics_list, key=lambda m: m.get("timestampGMT") or 0)[-1]
        ts = parse_gmt_ms(w.get("timestampGMT"))
        weight_g = _num(w.get("weight"))
        muscle_g = _num(w.get("muscleMass"))
        bone_g = _num(w.get("boneMass"))
        for m in (
            metric(d, M_WEIGHT, weight_g / 1000 if weight_g else None, ts=ts),
            metric(d, M_BMI, w.get("bmi"), ts=ts),
            metric(d, M_BODY_FAT, w.get("bodyFat"), ts=ts),
            metric(d, M_BODY_WATER, w.get("bodyWater"), ts=ts),
            metric(d, M_MUSCLE_MASS, muscle_g / 1000 if muscle_g else None, ts=ts),
            metric(d, M_BONE_MASS, bone_g / 1000 if bone_g else None, ts=ts),
        ):
            if m:
                out.append(m)
    return out


def map_blood_pressure_range(payload: Any) -> list[dict[str, Any]]:
    out = []
    for summary in (payload or {}).get("measurementSummaries") or []:
        for bp in summary.get("measurements") or []:
            ts_str = bp.get("measurementTimestampLocal") or bp.get("measurementTimestampGMT")
            dt = parse_naive(ts_str)
            if not dt:
                continue
            d = dt.strftime("%Y-%m-%d")
            ts = parse_gmt_ms(bp.get("measurementTimestampGMT"))
            for m in (
                metric(d, M_BP_SYS, bp.get("systolic"), ts=ts),
                metric(d, M_BP_DIA, bp.get("diastolic"), ts=ts),
                metric(d, M_BP_PULSE, bp.get("pulse"), ts=ts),
            ):
                if m:
                    out.append(m)
    return out


def map_lactate_threshold_latest(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    d = payload.get("calendarDate")
    if not d:
        return []
    return [m for m in (
        metric(d[:10], M_LT_HR, payload.get("heartRate")),
        metric(d[:10], M_LT_SPEED, payload.get("speed")),
    ) if m]


# ---------------------------------------------------------------- activities
def map_activity(a: dict[str, Any]) -> dict[str, Any] | None:
    aid = a.get("activityId")
    if aid is None:
        return None
    start_ts = parse_gmt_ms(a.get("beginTimestamp")) or parse_gmt_ms(a.get("startTimeGMT"))
    if start_ts is None:
        return None
    start_local = a.get("startTimeLocal")
    local_dt = parse_naive(start_local)
    date = local_dt.strftime("%Y-%m-%d") if local_dt else a.get("startTimeGMT", "")[:10]
    type_key = (a.get("activityType") or {}).get("typeKey")
    duration = _num(a.get("duration"))
    row = {
        "activity_id": int(aid),
        "date": date,
        "start_ts": start_ts,
        "start_local": start_local,
        "name": a.get("activityName"),
        "description": a.get("description"),
        "sport_type": type_key,
        "sport_category": categorize(type_key),
        "duration_s": duration,
        "elapsed_s": _num(a.get("elapsedDuration")) or duration,
        "moving_s": _num(a.get("movingDuration")),
        "distance_m": _num(a.get("distance")),
        "avg_speed_mps": _num(a.get("averageSpeed")),
        "max_speed_mps": _num(a.get("maxSpeed")),
        "calories": _num(a.get("calories")),
        "bmr_calories": _num(a.get("bmrCalories")),
        "avg_hr": _int(a.get("averageHR")),
        "max_hr": _int(a.get("maxHR")),
        "elevation_gain_m": _num(a.get("elevationGain")),
        "elevation_loss_m": _num(a.get("elevationLoss")),
        "avg_cadence": _num(a.get("averageRunningCadenceInStepsPerMinute") or a.get("averageBikingCadenceInRevPerMinute") or a.get("averageSwimCadenceInStrokesPerMinute")),
        "max_cadence": _num(a.get("maxRunningCadenceInStepsPerMinute") or a.get("maxBikingCadenceInRevPerMinute")),
        "avg_power": _num(a.get("avgPower")),
        "max_power": _num(a.get("maxPower")),
        "normalized_power": _num(a.get("normPower")),
        "aerobic_te": _num(a.get("aerobicTrainingEffect")),
        "anaerobic_te": _num(a.get("anaerobicTrainingEffect")),
        "training_load": _num(a.get("activityTrainingLoad")),
        "vo2max": _num(a.get("vO2MaxValue")),
        "moderate_min": _int(a.get("moderateIntensityMinutes")),
        "vigorous_min": _int(a.get("vigorousIntensityMinutes")),
        "steps": _int(a.get("steps")),
        "lap_count": _int(a.get("lapCount")),
        "hr_zone_1_s": _num(a.get("hrTimeInZone_1")),
        "hr_zone_2_s": _num(a.get("hrTimeInZone_2")),
        "hr_zone_3_s": _num(a.get("hrTimeInZone_3")),
        "hr_zone_4_s": _num(a.get("hrTimeInZone_4")),
        "hr_zone_5_s": _num(a.get("hrTimeInZone_5")),
        "has_polyline": 1 if a.get("hasPolyline") else 0,
        "location_name": a.get("locationName"),
        "device_id": _int(a.get("deviceId")),
        "raw_json": json.dumps(a, separators=(",", ":"), default=str),
        "updated_at": now_iso(),
    }
    return row


def map_hr_zone_boundaries(payload: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    zones = payload if isinstance(payload, list) else (payload or {}).get("zones") if isinstance(payload, dict) else []
    for z in zones or []:
        n = z.get("zoneNumber")
        low = z.get("zoneLowBoundary")
        if n is not None and low is not None and 1 <= int(n) <= 5:
            out[f"hr_zone_low_{int(n)}"] = int(low)
            secs = z.get("secsInZone")
            if secs is not None:
                out[f"hr_zone_{int(n)}_s"] = float(secs)
    return out


def map_exercise_sets(activity_id: int, payload: Any) -> list[dict[str, Any]]:
    sets = (payload or {}).get("exerciseSets") if isinstance(payload, dict) else payload
    rows = []
    for idx, s in enumerate(sets or []):
        if not isinstance(s, dict):
            continue
        ex = (s.get("exercises") or [{}])[0] or {}
        weight_g = _num(s.get("weight"))
        rows.append({
            "activity_id": activity_id,
            "set_index": idx,
            "start_ts": parse_gmt_ms(s.get("startTime")),
            "set_type": s.get("setType"),
            "exercise_category": ex.get("category"),
            "exercise_name": ex.get("name"),
            "reps": _int(s.get("repetitionCount")),
            "weight_kg": round(weight_g / 1000, 3) if weight_g else None,
            "duration_s": _num(s.get("duration")),
        })
    return rows
