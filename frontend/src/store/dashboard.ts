import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { addDays, todayStr } from '@/lib/format';

export type RangePreset = '24h' | '7d' | '30d' | '90d' | '1y' | 'custom';

export interface DateRange {
  start: string; // YYYY-MM-DD inclusive
  end: string;
}

const PRESET_DAYS: Record<Exclude<RangePreset, 'custom'>, number> = {
  '24h': 1,
  '7d': 7,
  '30d': 30,
  '90d': 90,
  '1y': 365,
};

export function rangeForPreset(preset: Exclude<RangePreset, 'custom'>, end = todayStr()): DateRange {
  return { start: addDays(end, -(PRESET_DAYS[preset] - 1)), end };
}

interface DashboardState {
  preset: RangePreset;
  range: DateRange;
  activeDate: string; // inspection date (clicking heatmap cell etc.)
  timezone: string; // IANA zone or 'local'
  selectedActivityId: number | null;
  collapsedRows: Record<string, boolean>;

  setPreset: (p: Exclude<RangePreset, 'custom'>) => void;
  setCustomRange: (r: DateRange) => void;
  setActiveDate: (d: string) => void;
  setTimezone: (tz: string) => void;
  selectActivity: (id: number | null) => void;
  toggleRow: (id: string) => void;
}

export const useDashboard = create<DashboardState>()(
  persist(
    (set) => ({
      preset: '7d',
      range: rangeForPreset('7d'),
      activeDate: todayStr(),
      timezone: 'local',
      selectedActivityId: null,
      collapsedRows: {},

      setPreset: (preset) => set({ preset, range: rangeForPreset(preset), activeDate: todayStr() }),
      setCustomRange: (range) => set({ preset: 'custom', range, activeDate: range.end }),
      setActiveDate: (activeDate) =>
        set((s) => {
          // Keep the inspection date inside the visible window.
          if (activeDate < s.range.start || activeDate > s.range.end) {
            const days = Math.max(1, Math.round((Date.parse(s.range.end) - Date.parse(s.range.start)) / 86400000) + 1);
            return { activeDate, preset: 'custom', range: { start: addDays(activeDate, -(days - 1)), end: activeDate } };
          }
          return { activeDate };
        }),
      setTimezone: (timezone) => set({ timezone }),
      selectActivity: (selectedActivityId) => set({ selectedActivityId }),
      toggleRow: (id) => set((s) => ({ collapsedRows: { ...s.collapsedRows, [id]: !s.collapsedRows[id] } })),
    }),
    {
      name: 'fitdash-dashboard',
      partialize: (s) => ({ timezone: s.timezone, collapsedRows: s.collapsedRows, preset: s.preset }),
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<DashboardState>;
        const preset = p.preset && p.preset !== 'custom' ? p.preset : '7d';
        return { ...current, ...p, preset, range: rangeForPreset(preset), activeDate: todayStr() };
      },
    },
  ),
);
