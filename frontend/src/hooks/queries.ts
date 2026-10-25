import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useDashboard } from '@/store/dashboard';
import { addDays } from '@/lib/format';

export const useAuthStatus = () =>
  useQuery({ queryKey: ['auth'], queryFn: api.authStatus, refetchInterval: 30_000 });

export const useSyncStatus = () =>
  useQuery({ queryKey: ['sync', 'status'], queryFn: api.syncStatus, refetchInterval: 15_000 });

export const useSettings = () => useQuery({ queryKey: ['settings'], queryFn: api.settings, staleTime: 60_000 });

export function useOverview() {
  const date = useDashboard((s) => s.activeDate);
  return useQuery({ queryKey: ['overview', date], queryFn: () => api.overview(date) });
}

export function useDaily() {
  const { start, end } = useDashboard((s) => s.range);
  return useQuery({ queryKey: ['daily', start, end], queryFn: () => api.daily(start, end) });
}

/** Intraday series for the visible range (server downsamples for long windows). */
export function useIntraday() {
  const { start, end } = useDashboard((s) => s.range);
  return useQuery({ queryKey: ['intraday', start, end], queryFn: () => api.intraday(start, end) });
}

export function useHourlySteps() {
  const { start, end } = useDashboard((s) => s.range);
  return useQuery({ queryKey: ['hourlySteps', start, end], queryFn: () => api.hourlySteps(start, end) });
}

export function useSleepDetail() {
  const date = useDashboard((s) => s.activeDate);
  return useQuery({ queryKey: ['sleepDetail', date], queryFn: () => api.sleepDetail(date) });
}

/** 53 weeks ending on the active date's week — feeds the contribution grid + habit matrix. */
export function useCalendar() {
  const end = useDashboard((s) => s.range.end);
  const start = addDays(end, -(53 * 7 + 7));
  return useQuery({ queryKey: ['calendar', start, end], queryFn: () => api.calendar(start, end), staleTime: 30_000 });
}

export function useActivities(category?: string, q?: string) {
  const { start, end } = useDashboard((s) => s.range);
  return useQuery({ queryKey: ['activities', start, end, category ?? 'all', q ?? ''], queryFn: () => api.activities(start, end, category, q) });
}

export function useActivityDetail(id: number | null) {
  return useQuery({ queryKey: ['activity', id], queryFn: () => api.activity(id as number), enabled: id !== null });
}
