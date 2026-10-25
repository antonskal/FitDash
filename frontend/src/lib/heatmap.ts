import type { CalendarActivity, CalendarDay, SportCategory } from '@/api/types';
import { addDays, dayjs, durationShort, hms, km, num } from '@/lib/format';

export type HeatFilter = 'all' | SportCategory | 'steps';
export type Intensity = 'duration' | 'calories' | 'load' | 'distance' | 'steps' | 'sleep';

export const FILTERS: { id: HeatFilter; label: string }[] = [
  { id: 'all', label: 'All Activities' },
  { id: 'running', label: 'Running' },
  { id: 'cycling', label: 'Cycling' },
  { id: 'swimming', label: 'Swimming' },
  { id: 'strength', label: 'Strength' },
  { id: 'yoga', label: 'Yoga' },
  { id: 'steps', label: 'Daily Step Goal' },
];

export const INTENSITIES: { id: Intensity; label: string }[] = [
  { id: 'duration', label: 'Workout Duration' },
  { id: 'calories', label: 'Active Calories' },
  { id: 'load', label: 'Training Load' },
  { id: 'distance', label: 'Distance' },
  { id: 'steps', label: 'Daily Steps' },
  { id: 'sleep', label: 'Sleep Score' },
];

export function filteredActivities(day: CalendarDay, filter: HeatFilter): CalendarActivity[] {
  if (filter === 'all' || filter === 'steps') return day.activities;
  return day.activities.filter((a) => a.category === filter);
}

export function cellValue(day: CalendarDay, filter: HeatFilter, intensity: Intensity): number {
  if (filter === 'steps' || intensity === 'steps') return day.steps ?? 0;
  if (intensity === 'sleep') return day.sleepScore ?? 0;
  const acts = filteredActivities(day, filter);
  switch (intensity) {
    case 'duration':
      return acts.reduce((s, a) => s + (a.durationS ?? 0), 0) / 60;
    case 'calories':
      return acts.reduce((s, a) => s + (a.calories ?? 0), 0);
    case 'load':
      return acts.reduce((s, a) => s + (a.trainingLoad ?? 0), 0);
    case 'distance':
      return acts.reduce((s, a) => s + (a.distanceM ?? 0), 0);
    default:
      return 0;
  }
}

export function quantileThresholds(values: number[]): number[] {
  const nz = values.filter((v) => v > 0).sort((a, b) => a - b);
  if (!nz.length) return [0, 0, 0, 0];
  const q = (p: number) => nz[Math.min(nz.length - 1, Math.round(p * (nz.length - 1)))];
  return [q(0.2), q(0.4), q(0.65), q(0.85)];
}

export function intensityLevel(v: number, thresholds: number[]): number {
  if (v <= 0) return 0;
  if (v <= thresholds[0]) return 1;
  if (v <= thresholds[1]) return 2;
  if (v <= thresholds[2]) return 3;
  return 4;
}

/** Monday of the ISO-like week containing `date` (Mon–Sun). */
export function mondayOf(date: string): string {
  const d = dayjs(date);
  const dow = d.day();
  const offset = dow === 0 ? -6 : 1 - dow;
  return d.add(offset, 'day').format('YYYY-MM-DD');
}

export function buildWeeks(end: string, weekCount = 52): string[][] {
  const lastMonday = dayjs(mondayOf(end));
  const firstMonday = lastMonday.subtract(weekCount - 1, 'week');
  return Array.from({ length: weekCount }, (_, w) => {
    const mon = firstMonday.add(w, 'week');
    return Array.from({ length: 7 }, (_, i) => mon.add(i, 'day').format('YYYY-MM-DD'));
  });
}

export type HabitId = 'running' | 'cycling' | 'swimming' | 'strength' | 'yoga' | 'steps' | 'sleep';

export const HABITS: { id: HabitId; label: string }[] = [
  { id: 'running', label: 'Run' },
  { id: 'cycling', label: 'Ride' },
  { id: 'swimming', label: 'Swim' },
  { id: 'strength', label: 'Strength' },
  { id: 'yoga', label: 'Mobility/Yoga' },
  { id: 'steps', label: 'Steps ≥ Goal' },
  { id: 'sleep', label: 'Sleep Score ≥ 80' },
];

export function habitDone(day: CalendarDay, habit: HabitId, sleepThreshold = 80): boolean {
  if (habit === 'steps') return (day.steps ?? 0) >= (day.stepGoal || 10000);
  if (habit === 'sleep') return (day.sleepScore ?? 0) >= sleepThreshold;
  return day.activities.some((a) => a.category === habit);
}

export function streakStats(days: CalendarDay[], habit: HabitId, asOf: string, sleepThreshold = 80) {
  const sorted = days.filter((d) => d.date <= asOf).sort((a, b) => a.date.localeCompare(b.date));
  let best = 0;
  let run = 0;
  for (const d of sorted) {
    if (habitDone(d, habit, sleepThreshold)) {
      run += 1;
      if (run > best) best = run;
    } else {
      run = 0;
    }
  }
  let current = 0;
  for (let i = sorted.length - 1; i >= 0; i--) {
    if (sorted[i].date === asOf && !habitDone(sorted[i], habit, sleepThreshold)) continue;
    if (habitDone(sorted[i], habit, sleepThreshold)) current += 1;
    else break;
  }
  return { current, best };
}

export function completionRate(
  days: CalendarDay[],
  habit: HabitId,
  end: string,
  n: number,
  sleepThreshold = 80,
): number {
  const start = addDays(end, -(n - 1));
  const window = days.filter((d) => d.date >= start && d.date <= end);
  if (!window.length) return 0;
  return window.filter((d) => habitDone(d, habit, sleepThreshold)).length / window.length;
}

export function dayTooltip(day: CalendarDay, filter: HeatFilter): { title: string; lines: string[] } {
  const acts = filteredActivities(day, filter);
  const dur = acts.reduce((s, a) => s + (a.durationS ?? 0), 0);
  const dist = acts.reduce((s, a) => s + (a.distanceM ?? 0), 0);
  const cal = acts.reduce((s, a) => s + (a.calories ?? 0), 0);
  const hrs = acts.map((a) => a.avgHr).filter((v): v is number => v != null);
  const avgHr = hrs.length ? Math.round(hrs.reduce((s, v) => s + v, 0) / hrs.length) : null;
  const names = acts.map((a) => a.name || a.type || a.category).slice(0, 4);
  const lines = [
    names.length ? names.join(' · ') : filter === 'steps' ? 'No workouts' : 'Rest / no matching activity',
    `Duration ${hms(dur)}  ·  ${km(dist)}  ·  ${num(cal, 0)} kcal`,
    `Avg HR ${avgHr ?? '—'}  ·  Steps ${num(day.steps)} / ${num(day.stepGoal)}`,
    `Sleep ${day.sleepScore ?? '—'}  ·  ${durationShort(day.sleepS)}`,
  ];
  return { title: dayjs(day.date).format('ddd, MMM D YYYY'), lines };
}
