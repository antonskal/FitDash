import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);

export { dayjs };

const pad = (n: number) => String(n).padStart(2, '0');

/** Seconds → HH:MM:SS (always three groups). */
export function hms(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—';
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${pad(h)}:${pad(m)}:${pad(s % 60)}`;
}

/** Seconds → "7h 42m" style. */
export function durationShort(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—';
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  if (h === 0) return `${m}m`;
  return `${h}h ${pad(m)}m`;
}

export function num(v: number | null | undefined, digits = 0, suffix = ''): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  return `${v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}${suffix}`;
}

export function km(meters: number | null | undefined, digits = 2): string {
  if (meters === null || meters === undefined) return '—';
  return `${(meters / 1000).toFixed(digits)} km`;
}

/** m/s → min:sec per km. */
export function pace(mps: number | null | undefined): string {
  if (!mps || mps <= 0) return '—';
  const secPerKm = 1000 / mps;
  let m = Math.floor(secPerKm / 60);
  let s = Math.round(secPerKm % 60);
  if (s === 60) {
    m += 1;
    s = 0;
  }
  return `${m}:${pad(s)} /km`;
}

export function paceSeconds(mps: number | null | undefined): number | null {
  if (!mps || mps <= 0) return null;
  return 1000 / mps;
}

export function speedKmh(mps: number | null | undefined, digits = 1): string {
  if (mps === null || mps === undefined) return '—';
  return `${(mps * 3.6).toFixed(digits)} km/h`;
}

export function signed(v: number | null | undefined, digits = 1, suffix = ''): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(digits)}${suffix}`;
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined) return '—';
  return `${v.toFixed(digits)}%`;
}

export function relative(iso: string | null | undefined): string {
  if (!iso) return 'never';
  return dayjs(iso).fromNow();
}

export function titleCase(s: string | null | undefined): string {
  if (!s) return '';
  return s
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format an epoch-ms timestamp in the given IANA zone ("local" = browser). */
export function fmtTs(ms: number, tz: string, fmt = 'HH:mm'): string {
  const d = tz === 'local' ? dayjs(ms) : dayjs(ms).tz(tz);
  return d.format(fmt);
}

export function tzDate(ms: number, tz: string): dayjs.Dayjs {
  return tz === 'local' ? dayjs(ms) : dayjs(ms).tz(tz);
}

/** Convert an epoch-ms timestamp into a "fake local" ms so ECharts time axes render in the chosen tz. */
export function toTzEpoch(ms: number, tz: string): number {
  if (tz === 'local') return ms;
  const d = dayjs(ms).tz(tz);
  return Date.UTC(d.year(), d.month(), d.date(), d.hour(), d.minute(), d.second(), d.millisecond());
}

export const todayStr = () => dayjs().format('YYYY-MM-DD');
export const addDays = (date: string, n: number) => dayjs(date).add(n, 'day').format('YYYY-MM-DD');
export const fmtDate = (date: string, fmt = 'ddd, MMM D') => dayjs(date).format(fmt);
