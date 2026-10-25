import type {
  ActivitiesResponse,
  ActivityDetail,
  AuthStatus,
  CalendarResponse,
  DailyRow,
  HourlyStepsCell,
  Intraday,
  Overview,
  Settings,
  SleepDetail,
  SyncStatus,
} from './types';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const qs = (params: Record<string, string | number | undefined | null>) => {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : '';
};

export const api = {
  // auth
  authStatus: () => request<AuthStatus>('/api/auth/status'),
  login: (email: string, password: string) =>
    request<AuthStatus>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  mfa: (code: string) => request<AuthStatus>('/api/auth/mfa', { method: 'POST', body: JSON.stringify({ code }) }),
  logout: () => request<AuthStatus>('/api/auth/logout', { method: 'POST' }),

  // sync
  syncStatus: () => request<SyncStatus>('/api/sync/status'),
  startSync: (body: { lookbackDays?: number; startDate?: string; endDate?: string; reprocessFit?: boolean }) =>
    request<{ runId: number }>('/api/sync/start', { method: 'POST', body: JSON.stringify(body) }),
  cancelSync: () => request<{ cancelled: boolean }>('/api/sync/cancel', { method: 'POST' }),

  // data
  settings: () => request<Settings>('/api/settings'),
  overview: (date: string) => request<Overview>(`/api/overview${qs({ date })}`),
  daily: (start: string, end: string) => request<{ days: DailyRow[] }>(`/api/daily${qs({ start, end })}`),
  intraday: (start: string, end: string) => request<Intraday>(`/api/intraday${qs({ start, end })}`),
  hourlySteps: (start: string, end: string) =>
    request<{ cells: HourlyStepsCell[] }>(`/api/steps/hourly${qs({ start, end })}`),
  sleepDetail: (date: string) => request<SleepDetail>(`/api/sleep/detail${qs({ date })}`),
  metric: (metric: string, start: string, end: string) =>
    request<{ metric: string; points: [string, number][] }>(`/api/metrics/${metric}${qs({ start, end })}`),
  calendar: (start: string, end: string) => request<CalendarResponse>(`/api/calendar${qs({ start, end })}`),
  activities: (start: string, end: string, category?: string, q?: string) =>
    request<ActivitiesResponse>(`/api/activities${qs({ start, end, category, q })}`),
  activity: (id: number) => request<ActivityDetail>(`/api/activities/${id}`),
};
