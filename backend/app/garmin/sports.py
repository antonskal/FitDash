"""Normalise Garmin's ~100 activity `typeKey`s into dashboard sport categories."""

from __future__ import annotations

CATEGORIES = ("running", "cycling", "swimming", "strength", "yoga", "walking", "hiking", "cardio", "other")

_CATEGORY_BY_PREFIX: dict[str, str] = {
    "running": "running",
    "run": "running",
    "trail_running": "running",
    "treadmill_running": "running",
    "indoor_running": "running",
    "track_running": "running",
    "virtual_run": "running",
    "ultra_run": "running",
    "obstacle_run": "running",
    "street_running": "running",
    "cycling": "cycling",
    "road_biking": "cycling",
    "mountain_biking": "cycling",
    "indoor_cycling": "cycling",
    "virtual_ride": "cycling",
    "gravel_cycling": "cycling",
    "cyclocross": "cycling",
    "e_bike_fitness": "cycling",
    "e_bike_mountain": "cycling",
    "bmx": "cycling",
    "track_cycling": "cycling",
    "recumbent_cycling": "cycling",
    "bike_commute": "cycling",
    "lap_swimming": "swimming",
    "open_water_swimming": "swimming",
    "swimming": "swimming",
    "strength_training": "strength",
    "indoor_climbing": "strength",
    "bouldering": "strength",
    "yoga": "yoga",
    "pilates": "yoga",
    "breathwork": "yoga",
    "meditation": "yoga",
    "flexibility_training": "yoga",
    "stretching": "yoga",
    "mobility": "yoga",
    "walking": "walking",
    "casual_walking": "walking",
    "speed_walking": "walking",
    "indoor_walking": "walking",
    "hiking": "hiking",
    "mountaineering": "hiking",
    "trail_hiking": "hiking",
    "rucking": "hiking",
    "hiit": "cardio",
    "indoor_cardio": "cardio",
    "cardio": "cardio",
    "elliptical": "cardio",
    "stair_climbing": "cardio",
    "indoor_rowing": "cardio",
    "rowing": "cardio",
    "jump_rope": "cardio",
    "fitness_equipment": "cardio",
}


def categorize(type_key: str | None) -> str:
    if not type_key:
        return "other"
    key = type_key.lower()
    if key in _CATEGORY_BY_PREFIX:
        return _CATEGORY_BY_PREFIX[key]
    for prefix, cat in _CATEGORY_BY_PREFIX.items():
        if key.startswith(prefix):
            return cat
    if "run" in key:
        return "running"
    if "cycl" in key or "bik" in key:
        return "cycling"
    if "swim" in key:
        return "swimming"
    if "strength" in key:
        return "strength"
    if "yoga" in key or "pilates" in key:
        return "yoga"
    if "walk" in key:
        return "walking"
    if "hik" in key:
        return "hiking"
    return "other"
