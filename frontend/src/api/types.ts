// API response shapes (mirror backend/app/services + routes).

export type AuthState = 'unauthenticated' | 'needs_mfa' | 'authenticated';

export interface AuthStatus {
  state: AuthState;
  displayName: string | null;
  email: string | null;
  message: string | null;
  tokenDir: string;
}

export interface SyncLive {
  type?: string;
  runId: number | null;
  mode: 'initial' | 'delta' | 'manual' | null;
  status: 'idle' | 'running' | 'ok' | 'error' | 'cancelled';
  phase: 'range' | 'daily' | 'activities' | 'finalize' | null;
  message: string;
  currentDate: string | null;
  startDate: string | null;
  endDate: string | null;
  daysTotal: number;
  daysDone: number;
  activitiesTotal: number;
  activitiesNew: number;
  activitiesDone: number;
  errors: number;
  startedAt: string | null;
  finishedAt: string | null;
  error: string | null;
  recentLog: string[];
}

export interface SyncMetadataRow {
  metric_domain: string;
  last_synced_date: string | null;
  last_synced_timestamp: string | null;
  status: string;
  message: string | null;
}

export interface SyncPlan {
  mode: 'initial' | 'delta' | 'manual';
  startDate: string;
  endDate: string;
  days: number;
  watermark: string | null;
}

export interface SyncStatus {
  live: SyncLive;
  isRunning: boolean;
  isFirstSync: boolean;
  watermark: string | null;
  lastSyncedAt: string | null;
  metadata: SyncMetadataRow[];
  lastRun: Record<string, unknown> | null;
  plan: SyncPlan | null;
  defaults: { lookbackDays: number };
}

export interface Settings {
  stepGoal: number;
  sleepScoreHabitThreshold: number;
  weeklyIntensityTargetMin: number;
  defaultTimezone: string;
  fitDownloadEnabled: boolean;
  bounds: { firstDate: string | null; lastDate: string | null; days: number; activities: number };
}

export interface MetricValue {
  value: number | null;
  text: string | null;
  date: string;
}

export interface Overview {
  date: string;
  readiness: {
    sleepScore: number | null;
    sleepQualifier: string | null;
    totalSleepS: number | null;
    bodyBattery: {
      current: number | null;
      charged: number | null;
      drained: number | null;
      highest: number | null;
      lowest: number | null;
      atWake: number | null;
    };
    trainingReadiness: MetricValue | null;
    trainingReadinessLevel: MetricValue | null;
    recoveryTimeH: MetricValue | null;
    hrv: {
      lastNight: number | null;
      weeklyAvg: number | null;
      sevenDayMean: number | null;
      status: string | null;
      baselineLow: number | null;
      baselineHigh: number | null;
    };
    restingHr: number | null;
    restingHr7d: number | null;
    avgStress: number | null;
    trainingStatus: MetricValue | null;
    weeklyLoad: MetricValue | null;
    acwr: MetricValue | null;
  };
  performance: {
    vo2maxRunning: MetricValue | null;
    vo2maxCycling: MetricValue | null;
    fitnessAge: MetricValue | null;
    enduranceScore: MetricValue | null;
    hillScore: MetricValue | null;
    hillStrength: MetricValue | null;
    hillEndurance: MetricValue | null;
    lactateThresholdHr: MetricValue | null;
    lactateThresholdSpeedMps: MetricValue | null;
    race: { '5k': MetricValue | null; '10k': MetricValue | null; half: MetricValue | null; marathon: MetricValue | null };
  };
  daily: {
    steps: number | null;
    stepGoal: number;
    distanceM: number | null;
    activeKcal: number | null;
    restingKcal: number | null;
    totalKcal: number | null;
    moderateMin: number | null;
    vigorousMin: number | null;
    floorsUp: number | null;
    hydrationMl: number | null;
    hydrationGoalMl: number | null;
    sweatLossMl: number | null;
    bloodPressure: { systolic: MetricValue | null; diastolic: MetricValue | null; pulse: MetricValue | null };
    body: {
      weightKg: MetricValue | null;
      bmi: MetricValue | null;
      bodyFatPct: MetricValue | null;
      bodyWaterPct: MetricValue | null;
      muscleMassKg: MetricValue | null;
      boneMassKg: MetricValue | null;
    };
    spo2Avg: number | null;
    spo2Lowest: number | null;
    respirationAvg: number | null;
    skinTempDevC: number | null;
    skinTempDevF: number | null;
  };
}

export interface DailyRow {
  date: string;
  total_steps?: number | null;
  step_goal?: number | null;
  total_distance_m?: number | null;
  active_kcal?: number | null;
  bmr_kcal?: number | null;
  moderate_intensity_min?: number | null;
  vigorous_intensity_min?: number | null;
  intensity_goal_min?: number | null;
  resting_hr?: number | null;
  min_hr?: number | null;
  max_hr?: number | null;
  avg_stress?: number | null;
  body_battery_charged?: number | null;
  body_battery_drained?: number | null;
  avg_spo2?: number | null;
  lowest_spo2?: number | null;
  avg_respiration?: number | null;
  avg_skin_temp_dev_c?: number | null;
  avg_skin_temp_dev_f?: number | null;
  sleep_score?: number | null;
  total_sleep_s?: number | null;
  deep_s?: number | null;
  light_s?: number | null;
  rem_s?: number | null;
  awake_s?: number | null;
  sleep_start_ts?: number | null;
  sleep_end_ts?: number | null;
  sleep_avg_hrv?: number | null;
  sleep_avg_spo2?: number | null;
  sleep_lowest_spo2?: number | null;
  sleep_avg_respiration?: number | null;
  sleep_avg_movement?: number | null;
  sleep_skin_temp_dev_c?: number | null;
  sleep_skin_temp_dev_f?: number | null;
  restless_moments?: number | null;
  awake_count?: number | null;
  metrics: Record<string, number>;
}

export type Series = [number, number][];

export interface Intraday {
  start: string;
  end: string;
  bucketMs: number;
  hr: Series;
  stress: Series;
  bodyBattery: Series;
  respiration: Series;
  spo2: Series;
  hrv: Series;
}

export interface HourlyStepsCell {
  date: string;
  hour: number;
  steps: number;
}

export interface SleepDetail {
  session: Record<string, number | string | null> | null;
  stages: [number, number, number][];
  movement: Series;
  spo2: Series;
  respiration: Series;
  hrv: Series;
  hr: Series;
}

export interface CalendarActivity {
  id: number;
  name: string | null;
  type: string | null;
  category: SportCategory;
  durationS: number | null;
  distanceM: number | null;
  calories: number | null;
  avgHr: number | null;
  trainingLoad: number | null;
  elevationGainM: number | null;
  startTs: number;
}

export interface CalendarDay {
  date: string;
  steps: number | null;
  stepGoal: number;
  sleepScore: number | null;
  sleepS: number | null;
  activities: CalendarActivity[];
}

export interface CalendarResponse {
  start: string;
  end: string;
  days: CalendarDay[];
}

export type SportCategory =
  | 'running'
  | 'cycling'
  | 'swimming'
  | 'strength'
  | 'yoga'
  | 'walking'
  | 'hiking'
  | 'cardio'
  | 'other';

export interface Activity {
  id: number;
  date: string;
  startTs: number;
  startLocal: string | null;
  name: string | null;
  type: string | null;
  category: SportCategory;
  durationS: number | null;
  elapsedS: number | null;
  movingS: number | null;
  distanceM: number | null;
  avgSpeedMps: number | null;
  maxSpeedMps: number | null;
  calories: number | null;
  avgHr: number | null;
  maxHr: number | null;
  elevationGainM: number | null;
  elevationLossM: number | null;
  avgCadence: number | null;
  avgPower: number | null;
  normalizedPower: number | null;
  aerobicTe: number | null;
  anaerobicTe: number | null;
  trainingLoad: number | null;
  vo2max: number | null;
  steps: number | null;
  lapCount: number | null;
  hrZones: { secondsInZone: (number | null)[]; lowBoundaries: (number | null)[] };
  hasPolyline: boolean;
  fitStatus: string;
  location: string | null;
}

export interface ActivitiesResponse {
  start: string;
  end: string;
  activities: Activity[];
  categories: { category: SportCategory; count: number; duration_s: number; distance_m: number; calories: number }[];
}

export interface Telemetry {
  elapsedS: number[];
  ts: (number | null)[];
  lat: (number | null)[];
  lon: (number | null)[];
  altitudeM: (number | null)[];
  distanceM: (number | null)[];
  speedMps: (number | null)[];
  hr: (number | null)[];
  cadence: (number | null)[];
  power: (number | null)[];
  temperatureC: (number | null)[];
  gradeAdjustedSpeedMps: (number | null)[];
}

export interface Lap {
  index: number;
  startTs: number | null;
  elapsedS: number | null;
  movingS: number | null;
  distanceM: number | null;
  avgHr: number | null;
  maxHr: number | null;
  avgSpeedMps: number | null;
  maxSpeedMps: number | null;
  avgPower: number | null;
  avgCadence: number | null;
  ascentM: number | null;
  descentM: number | null;
  calories: number | null;
}

export interface StrengthSet {
  index: number;
  startTs: number | null;
  type: string | null;
  exercise: string;
  category: string | null;
  name: string | null;
  reps: number | null;
  weightKg: number | null;
  durationS: number | null;
  e1rm: number | null;
}

export interface StrengthSummary {
  sets: StrengthSet[];
  perExercise: {
    exercise: string;
    category: string | null;
    name: string | null;
    sets: number;
    reps: number;
    volumeKg: number;
    maxWeightKg: number;
    best1rm: number | null;
  }[];
  perCategory: { category: string; volumeKg: number }[];
  totalVolumeKg: number;
  totalSets: number;
  totalReps: number;
  progression: Record<string, [string, number, number][]>;
}

export interface ActivityDetail {
  summary: Activity;
  telemetry: Telemetry;
  laps: Lap[];
  strength: StrengthSummary | null;
}
