from __future__ import annotations

from app.garmin import mappers as M
from app.garmin.sports import categorize


def test_daily_summary_maps_core_fields():
    stats = {
        "wellnessStartTimeGmt": "2026-08-14T04:00:00.0", "wellnessStartTimeLocal": "2026-08-14T00:00:00.0",
        "totalSteps": 8123, "dailyStepGoal": 10000, "activeKilocalories": 512.4, "bmrKilocalories": 1700,
        "restingHeartRate": 52, "bodyBatteryChargedValue": 61, "bodyBatteryDrainedValue": 55, "averageSpo2": 96.2,
    }
    row = M.map_daily_summary("2026-08-14", stats)
    assert row["total_steps"] == 8123
    assert row["resting_hr"] == 52
    assert row["body_battery_charged"] == 61
    assert M.daily_local_offset_ms(stats) == -4 * 3600 * 1000


def test_hourly_steps_buckets_by_local_hour():
    buckets = [
        {"startGMT": "2026-08-14T04:00:00.0", "steps": 10},   # 00:00 local (UTC-4)
        {"startGMT": "2026-08-14T04:15:00.0", "steps": 5},
        {"startGMT": "2026-08-14T13:30:00.0", "steps": 400},  # 09:30 local
        {"startGMT": "2026-08-14T13:45:00.0", "steps": None},
    ]
    rows = M.map_hourly_steps("2026-08-14", buckets, -4 * 3600 * 1000)
    assert rows == [{"date": "2026-08-14", "hour": 0, "steps": 15}, {"date": "2026-08-14", "hour": 9, "steps": 400}]


def test_intraday_stress_and_body_battery():
    payload = {"stressValuesArray": [[1000, 25], [2000, -1], [3000, None]],
               "bodyBatteryValuesArray": [[1000, "charging", 80, 1], [2000, "draining", 78, 1]]}
    stress, bb = M.map_intraday_stress("2026-08-14", payload)
    assert [s["stress"] for s in stress] == [25, -1]
    assert [b["level"] for b in bb] == [80, 78]
    assert bb[0]["status"] == "charging"


def test_sleep_mapping_produces_session_and_stages():
    payload = {
        "dailySleepDTO": {
            "calendarDate": "2026-08-14", "sleepStartTimestampGMT": 1755144000000, "sleepEndTimestampGMT": 1755172800000,
            "sleepTimeSeconds": 27000, "deepSleepSeconds": 6000, "lightSleepSeconds": 15000, "remSleepSeconds": 6000,
            "awakeSleepSeconds": 1800, "sleepScores": {"overall": {"value": 82, "qualifierKey": "GOOD"}},
        },
        "sleepLevels": [{"startGMT": "2026-08-14T04:00:00.0", "endGMT": "2026-08-14T04:30:00.0", "activityLevel": 1.0}],
        "avgOvernightHrv": 48.0, "restingHeartRate": 50,
        "wellnessEpochSPO2DataDTOList": [{"epochTimestamp": "2026-08-14T04:00:00.0", "spo2Reading": 96}],
    }
    out = M.map_sleep("2026-08-14", payload)
    assert out["session"]["sleep_score"] == 82
    assert out["session"]["avg_hrv"] == 48.0
    assert out["stages"][0]["stage"] == 1
    assert out["spo2"][0]["spo2"] == 96


def test_activity_mapping_and_categorisation():
    a = {"activityId": 123, "beginTimestamp": 1755144000000, "startTimeLocal": "2026-08-14 06:00:00",
         "activityName": "Morning Run", "activityType": {"typeKey": "trail_running"}, "duration": 3600.5,
         "distance": 10000, "averageHR": 150, "hrTimeInZone_3": 1200.0, "hasPolyline": True}
    row = M.map_activity(a)
    assert row["activity_id"] == 123
    assert row["date"] == "2026-08-14"
    assert row["sport_category"] == "running"
    assert row["hr_zone_3_s"] == 1200.0
    assert row["has_polyline"] == 1
    assert categorize("indoor_cycling") == "cycling"
    assert categorize("strength_training") == "strength"
    assert categorize("pilates") == "yoga"
    assert categorize("something_new") == "other"


def test_range_mappers_find_dated_lists():
    rp = [{"calendarDate": "2026-08-14", "time5K": 1320, "time10K": 2760, "timeHalfMarathon": 6100, "timeMarathon": 12900}]
    rows = M.map_race_predictions_range(rp)
    assert {r["metric"] for r in rows} == {M.M_RACE_5K, M.M_RACE_10K, M.M_RACE_HALF, M.M_RACE_FULL}
    hill = {"hillScoreDTOList": [{"calendarDate": "2026-08-14", "overallScore": 61, "strengthScore": 55, "enduranceScore": 67}]}
    assert len(M.map_hill_range(hill)) == 3
    weigh = {"dailyWeightSummaries": [{"summaryDate": "2026-08-14", "allWeightMetrics": [
        {"timestampGMT": 1755144000000, "weight": 78000, "bmi": 24.1, "bodyFat": 16.0, "muscleMass": 34000, "boneMass": 3400}]}]}
    w = {r["metric"]: r["value"] for r in M.map_weigh_ins_range(weigh)}
    assert w[M.M_WEIGHT] == 78.0 and w[M.M_MUSCLE_MASS] == 34.0


def test_exercise_sets_mapping():
    payload = {"exerciseSets": [
        {"setType": "ACTIVE", "startTime": "2026-08-14T06:00:00.0", "repetitionCount": 8, "weight": 60000, "duration": 30,
         "exercises": [{"category": "BENCH_PRESS", "name": "BARBELL_BENCH_PRESS"}]},
        {"setType": "REST", "duration": 90},
    ]}
    rows = M.map_exercise_sets(1, payload)
    assert rows[0]["weight_kg"] == 60.0 and rows[0]["reps"] == 8
    assert rows[1]["set_type"] == "REST"
