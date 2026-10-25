import type { SportCategory } from '@/api/types';

export const C = {
  carbon: '#0b0c0e',
  panel: '#181b1f',
  edge: '#22252b',
  edgeStrong: '#2c3038',
  ink: '#d8d9da',
  inkDim: '#9aa0a6',
  inkFaint: '#6e7378',
  green: '#73bf69',
  cyan: '#5ef2ff',
  yellow: '#fade2a',
  orange: '#ff9830',
  red: '#f2495c',
  blue: '#5794f2',
  purple: '#b877d9',
  pink: '#f26bb3',
  teal: '#32c5bf',
};

export const SPORT_COLOR: Record<SportCategory, string> = {
  running: C.orange,
  cycling: C.blue,
  swimming: C.cyan,
  strength: C.red,
  yoga: C.purple,
  walking: C.green,
  hiking: C.teal,
  cardio: C.pink,
  other: C.inkDim,
};

export const SPORT_LABEL: Record<SportCategory, string> = {
  running: 'Run',
  cycling: 'Ride',
  swimming: 'Swim',
  strength: 'Strength',
  yoga: 'Mobility/Yoga',
  walking: 'Walk',
  hiking: 'Hike',
  cardio: 'Cardio',
  other: 'Other',
};

/** 5-step Grafana-ish palettes for contribution grids. Index 0 = empty. */
export const PALETTES = {
  emerald: ['#1c2128', '#0e4429', '#006d32', '#26a641', '#39d353'],
  cyan: ['#1c2128', '#0b3a44', '#0f6b7a', '#19a7bd', '#5ef2ff'],
  amber: ['#1c2128', '#4a3a07', '#8a6a0c', '#c99a12', '#fade2a'],
  magma: ['#1c2128', '#3b0f4a', '#7a1f6f', '#c23b6a', '#f26bb3'],
} as const;
export type PaletteName = keyof typeof PALETTES;

export function scoreColor(v: number | null | undefined, good = 80, ok = 60): string {
  if (v === null || v === undefined) return C.inkFaint;
  if (v >= good) return C.green;
  if (v >= ok) return C.yellow;
  return C.red;
}

export function stressColor(v: number): string {
  if (v < 0) return C.inkFaint;
  if (v < 25) return C.blue;
  if (v < 50) return C.yellow;
  if (v < 75) return C.orange;
  return C.red;
}

export const HR_ZONE_COLORS = ['#9aa0a6', C.blue, C.green, C.yellow, C.orange, C.red];

/** Linear interpolation between gradient stops for metric-colored polylines. */
export function gradient(stops: string[], t: number): string {
  const x = Math.min(1, Math.max(0, t)) * (stops.length - 1);
  const i = Math.floor(x);
  const f = x - i;
  const a = hex(stops[i]);
  const b = hex(stops[Math.min(stops.length - 1, i + 1)]);
  const mix = a.map((c, k) => Math.round(c + (b[k] - c) * f));
  return `rgb(${mix[0]},${mix[1]},${mix[2]})`;
}

function hex(h: string): number[] {
  const s = h.replace('#', '');
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
}

export const METRIC_GRADIENTS = {
  hr: [C.blue, C.green, C.yellow, C.orange, C.red],
  pace: [C.red, C.orange, C.yellow, C.green, C.cyan],
  elevation: ['#1d4e89', '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51'],
  cadence: ['#3a3a8a', C.purple, C.pink],
  power: [C.blue, C.cyan, C.green, C.yellow, C.red],
};
