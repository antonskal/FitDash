-- FitDash SQLite schema.
-- Conventions:
--   * `date` columns are the user's local calendar date as reported by Garmin (YYYY-MM-DD).
--   * `*_ts` columns are UTC epoch milliseconds (INTEGER) so the frontend can
--     re-project them into any timezone.
--   * Every table that is re-fetched during delta syncs has a natural primary
--     key so `INSERT ... ON CONFLICT DO UPDATE` is idempotent.

PRAGMA foreign_keys = ON;

-- --------------------------------------------------------------------------
-- Sync bookkeeping
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_metadata (
    metric_domain          TEXT PRIMARY KEY,          -- e.g. 'daily', 'intraday', 'sleep', 'activities'
    last_synced_date       TEXT,                      -- YYYY-MM-DD (local) high-water mark
    last_synced_timestamp  TEXT,                      -- UTC ISO-8601 of the last successful run
    status                 TEXT NOT NULL DEFAULT 'idle', -- idle | running | ok | error
    message                TEXT
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mode          TEXT NOT NULL,                     -- initial | delta | manual
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL DEFAULT 'running',   -- running | ok | error | cancelled
    days_total    INTEGER NOT NULL DEFAULT 0,
    days_done     INTEGER NOT NULL DEFAULT 0,
    activities_new INTEGER NOT NULL DEFAULT 0,
    message       TEXT
);

CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- --------------------------------------------------------------------------
-- Daily aggregates
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_summaries (
    date                    TEXT PRIMARY KEY,
    wellness_start_ts       INTEGER,
    wellness_end_ts         INTEGER,
    total_steps             INTEGER,
    step_goal               INTEGER,
    total_distance_m        REAL,
    active_kcal             REAL,
    bmr_kcal                REAL,
    total_kcal              REAL,
    moderate_intensity_min  INTEGER,
    vigorous_intensity_min  INTEGER,
    intensity_goal_min      INTEGER,
    floors_ascended         REAL,
    floors_descended        REAL,
    highly_active_s         INTEGER,
    active_s                INTEGER,
    sedentary_s             INTEGER,
    sleeping_s              INTEGER,
    resting_hr              INTEGER,
    min_hr                  INTEGER,
    max_hr                  INTEGER,
    avg_stress              INTEGER,
    max_stress              INTEGER,
    stress_duration_s       INTEGER,
    rest_stress_s           INTEGER,
    low_stress_s            INTEGER,
    medium_stress_s         INTEGER,
    high_stress_s           INTEGER,
    body_battery_charged    INTEGER,
    body_battery_drained    INTEGER,
    body_battery_highest    INTEGER,
    body_battery_lowest     INTEGER,
    body_battery_at_wake    INTEGER,
    body_battery_most_recent INTEGER,
    avg_spo2                REAL,
    lowest_spo2             REAL,
    avg_respiration         REAL,
    lowest_respiration      REAL,
    highest_respiration     REAL,
    avg_skin_temp_dev_c     REAL,
    avg_skin_temp_dev_f     REAL,
    updated_at              TEXT NOT NULL
);

-- Sparse per-day scalar metrics (scores, body composition, predictions...).
-- Kept as key/value so new Garmin metrics never require a migration.
CREATE TABLE IF NOT EXISTS daily_metrics (
    date        TEXT NOT NULL,
    metric      TEXT NOT NULL,
    value       REAL,
    text_value  TEXT,
    source_ts   INTEGER,
    PRIMARY KEY (date, metric)
);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_metric_date ON daily_metrics (metric, date);

-- --------------------------------------------------------------------------
-- Intraday series
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intraday_hr (
    ts    INTEGER PRIMARY KEY,
    date  TEXT NOT NULL,
    hr    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intraday_hr_date ON intraday_hr (date);

CREATE TABLE IF NOT EXISTS intraday_stress (
    ts      INTEGER PRIMARY KEY,
    date    TEXT NOT NULL,
    stress  INTEGER NOT NULL          -- -1/-2 = unmeasurable per Garmin; stored for gap rendering
);
CREATE INDEX IF NOT EXISTS idx_intraday_stress_date ON intraday_stress (date);

CREATE TABLE IF NOT EXISTS intraday_body_battery (
    ts      INTEGER PRIMARY KEY,
    date    TEXT NOT NULL,
    level   INTEGER NOT NULL,
    status  TEXT                      -- charging | draining | measured...
);
CREATE INDEX IF NOT EXISTS idx_intraday_bb_date ON intraday_body_battery (date);

CREATE TABLE IF NOT EXISTS intraday_respiration (
    ts    INTEGER PRIMARY KEY,
    date  TEXT NOT NULL,
    brpm  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intraday_resp_date ON intraday_respiration (date);

CREATE TABLE IF NOT EXISTS intraday_spo2 (
    ts    INTEGER PRIMARY KEY,
    date  TEXT NOT NULL,
    spo2  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intraday_spo2_date ON intraday_spo2 (date);

CREATE TABLE IF NOT EXISTS hrv_readings (
    ts    INTEGER PRIMARY KEY,
    date  TEXT NOT NULL,
    hrv   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hrv_date ON hrv_readings (date);

CREATE TABLE IF NOT EXISTS hourly_steps (
    date   TEXT NOT NULL,
    hour   INTEGER NOT NULL,          -- 0..23, local hour
    steps  INTEGER NOT NULL,
    PRIMARY KEY (date, hour)
);

-- --------------------------------------------------------------------------
-- Sleep
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sleep_sessions (
    date                 TEXT PRIMARY KEY,   -- calendar date the sleep is attributed to (wake day)
    sleep_start_ts       INTEGER,
    sleep_end_ts         INTEGER,
    total_sleep_s        INTEGER,
    deep_s               INTEGER,
    light_s              INTEGER,
    rem_s                INTEGER,
    awake_s              INTEGER,
    unmeasurable_s       INTEGER,
    sleep_score          INTEGER,
    score_qualifier      TEXT,
    avg_spo2             REAL,
    lowest_spo2          REAL,
    highest_spo2         REAL,
    avg_respiration      REAL,
    lowest_respiration   REAL,
    highest_respiration  REAL,
    avg_hrv              REAL,
    resting_hr           INTEGER,
    avg_stress           REAL,
    restless_moments     INTEGER,
    awake_count          INTEGER,
    body_battery_change  INTEGER,
    skin_temp_dev_c      REAL,
    skin_temp_dev_f      REAL,
    avg_movement         REAL,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sleep_stages (
    date      TEXT NOT NULL,
    start_ts  INTEGER NOT NULL,
    end_ts    INTEGER NOT NULL,
    stage     INTEGER NOT NULL,       -- 0 deep, 1 light, 2 rem, 3 awake
    PRIMARY KEY (date, start_ts)
);

CREATE TABLE IF NOT EXISTS sleep_movement (
    ts     INTEGER PRIMARY KEY,
    date   TEXT NOT NULL,
    level  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sleep_movement_date ON sleep_movement (date);

-- --------------------------------------------------------------------------
-- Activities / workouts
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activities (
    activity_id          INTEGER PRIMARY KEY,
    date                 TEXT NOT NULL,      -- local calendar date of start
    start_ts             INTEGER NOT NULL,   -- UTC epoch ms
    start_local          TEXT,               -- Garmin local start "YYYY-MM-DD HH:MM:SS"
    name                 TEXT,
    description          TEXT,
    sport_type           TEXT,               -- Garmin typeKey (e.g. trail_running)
    sport_category       TEXT NOT NULL,      -- normalized: running|cycling|swimming|strength|yoga|walking|hiking|cardio|other
    duration_s           REAL,
    elapsed_s            REAL,
    moving_s             REAL,
    distance_m           REAL,
    avg_speed_mps        REAL,
    max_speed_mps        REAL,
    calories             REAL,
    bmr_calories         REAL,
    avg_hr               INTEGER,
    max_hr               INTEGER,
    elevation_gain_m     REAL,
    elevation_loss_m     REAL,
    avg_cadence          REAL,
    max_cadence          REAL,
    avg_power            REAL,
    max_power            REAL,
    normalized_power     REAL,
    aerobic_te           REAL,
    anaerobic_te         REAL,
    training_load        REAL,
    vo2max               REAL,
    moderate_min         INTEGER,
    vigorous_min         INTEGER,
    steps                INTEGER,
    lap_count            INTEGER,
    hr_zone_1_s          REAL,
    hr_zone_2_s          REAL,
    hr_zone_3_s          REAL,
    hr_zone_4_s          REAL,
    hr_zone_5_s          REAL,
    hr_zone_low_1        INTEGER,
    hr_zone_low_2        INTEGER,
    hr_zone_low_3        INTEGER,
    hr_zone_low_4        INTEGER,
    hr_zone_low_5        INTEGER,
    has_polyline         INTEGER NOT NULL DEFAULT 0,
    fit_status           TEXT NOT NULL DEFAULT 'pending',  -- pending | parsed | unavailable | skipped | error
    fit_parsed_at        TEXT,
    location_name        TEXT,
    device_id            INTEGER,
    raw_json             TEXT,
    updated_at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activities_date ON activities (date);
CREATE INDEX IF NOT EXISTS idx_activities_category_date ON activities (sport_category, date);

CREATE TABLE IF NOT EXISTS activity_telemetry_points (
    activity_id          INTEGER NOT NULL REFERENCES activities (activity_id) ON DELETE CASCADE,
    elapsed_s            REAL NOT NULL,
    ts                   INTEGER,
    lat                  REAL,
    lon                  REAL,
    altitude_m           REAL,
    distance_m           REAL,
    speed_mps            REAL,
    hr                   INTEGER,
    cadence              REAL,
    power                REAL,
    temperature_c        REAL,
    grade_adjusted_speed REAL,
    vertical_oscillation REAL,
    stance_time          REAL,
    step_length          REAL,
    PRIMARY KEY (activity_id, elapsed_s)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS activity_laps (
    activity_id   INTEGER NOT NULL REFERENCES activities (activity_id) ON DELETE CASCADE,
    lap_index     INTEGER NOT NULL,
    start_ts      INTEGER,
    elapsed_s     REAL,
    moving_s      REAL,
    distance_m    REAL,
    avg_hr        INTEGER,
    max_hr        INTEGER,
    avg_speed_mps REAL,
    max_speed_mps REAL,
    avg_power     REAL,
    avg_cadence   REAL,
    ascent_m      REAL,
    descent_m     REAL,
    calories      REAL,
    PRIMARY KEY (activity_id, lap_index)
);

CREATE TABLE IF NOT EXISTS strength_sets (
    activity_id        INTEGER NOT NULL REFERENCES activities (activity_id) ON DELETE CASCADE,
    set_index          INTEGER NOT NULL,
    start_ts           INTEGER,
    set_type           TEXT,                 -- ACTIVE | REST
    exercise_category  TEXT,
    exercise_name      TEXT,
    reps               INTEGER,
    weight_kg          REAL,
    duration_s         REAL,
    PRIMARY KEY (activity_id, set_index)
);
CREATE INDEX IF NOT EXISTS idx_strength_sets_exercise ON strength_sets (exercise_category, exercise_name);
