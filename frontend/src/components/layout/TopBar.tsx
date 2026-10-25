import { useState } from 'react';
import { Activity, Calendar, Globe, LogOut, RefreshCw, Settings2, X } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAuthStatus, useSyncStatus } from '@/hooks/queries';
import { useDashboard, type RangePreset } from '@/store/dashboard';
import { useSyncStream } from '@/store/sync';
import { relative } from '@/lib/format';
import SyncStatusBadge from '@/components/sync/SyncStatusBadge';

const PRESETS: Exclude<RangePreset, 'custom'>[] = ['24h', '7d', '30d', '90d', '1y'];

const TIMEZONES = [
  'local',
  'UTC',
  'America/Los_Angeles',
  'America/Denver',
  'America/Chicago',
  'America/New_York',
  'America/Sao_Paulo',
  'Europe/London',
  'Europe/Berlin',
  'Europe/Helsinki',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
];

interface TopBarProps {
  onOpenSync: () => void;
}

export default function TopBar({ onOpenSync }: TopBarProps) {
  const { preset, range, setPreset, setCustomRange, timezone, setTimezone } = useDashboard();
  const { data: auth } = useAuthStatus();
  const { data: sync } = useSyncStatus();
  const live = useSyncStream((s) => s.live);
  const qc = useQueryClient();
  const [custom, setCustom] = useState(false);
  const [draft, setDraft] = useState(range);

  const running = live?.status === 'running' || sync?.isRunning;
  const authed = auth?.state === 'authenticated';

  const syncNow = async () => {
    if (!authed) return onOpenSync();
    if (sync?.isFirstSync) return onOpenSync();
    try {
      await api.startSync({});
    } catch (e) {
      console.warn(e);
    } finally {
      qc.invalidateQueries({ queryKey: ['sync'] });
    }
  };

  const logout = async () => {
    await api.logout();
    qc.invalidateQueries();
  };

  return (
    <header className="sticky top-0 z-30 h-11 border-b border-edge bg-carbon/95 backdrop-blur flex items-center gap-3 px-3">
      <div className="flex items-center gap-2 mr-2">
        <Activity size={16} className="text-emerald" />
        <span className="font-semibold text-sm tracking-tight">FitDash</span>
        <span className="hidden sm:inline text-[10px] text-ink-faint uppercase tracking-wider">Garmin telemetry</span>
      </div>

      {/* Date range */}
      <div className="flex items-center gap-0.5 border border-edge-strong rounded-sm p-0.5">
        {PRESETS.map((p) => (
          <button
            key={p}
            onClick={() => {
              setCustom(false);
              setPreset(p);
            }}
            className={`h-6 px-2 text-[11px] rounded-[2px] num whitespace-nowrap ${preset === p ? 'bg-blue/20 text-blue' : 'text-ink-dim hover:text-ink hover:bg-panel-hover'}`}
          >
            {p === '24h' ? '24h' : p}
          </button>
        ))}
        <button
          onClick={() => {
            setDraft(range);
            setCustom((c) => !c);
          }}
          className={`h-6 px-2 text-[11px] rounded-[2px] flex items-center gap-1 ${preset === 'custom' ? 'bg-blue/20 text-blue' : 'text-ink-dim hover:text-ink hover:bg-panel-hover'}`}
        >
          <Calendar size={11} /> Custom
        </button>
      </div>
      {custom && (
        <div className="flex items-center gap-1 text-xs">
          <input type="date" className="input h-7 text-xs" value={draft.start} max={draft.end} onChange={(e) => setDraft({ ...draft, start: e.target.value })} />
          <span className="text-ink-faint">→</span>
          <input type="date" className="input h-7 text-xs" value={draft.end} min={draft.start} onChange={(e) => setDraft({ ...draft, end: e.target.value })} />
          <button
            className="btn btn-primary h-7"
            onClick={() => {
              if (draft.start && draft.end && draft.start <= draft.end) {
                setCustomRange(draft);
                setCustom(false);
              }
            }}
          >
            Apply
          </button>
          <button className="btn btn-ghost h-7 px-1" onClick={() => setCustom(false)}>
            <X size={12} />
          </button>
        </div>
      )}
      <span className="hidden lg:inline text-[11px] text-ink-faint num">
        {range.start} → {range.end}
      </span>

      <div className="flex-1" />

      {/* Timezone */}
      <label className="flex items-center gap-1 text-ink-dim">
        <Globe size={12} />
        <select className="select" value={timezone} onChange={(e) => setTimezone(e.target.value)} title="Timezone for intraday charts">
          {TIMEZONES.map((tz) => (
            <option key={tz} value={tz}>
              {tz === 'local' ? `Browser (${Intl.DateTimeFormat().resolvedOptions().timeZone})` : tz}
            </option>
          ))}
        </select>
      </label>

      {/* Sync status + button */}
      <SyncStatusBadge live={live} lastSyncedAt={sync?.lastSyncedAt ?? null} onClick={onOpenSync} />
      <button className="btn btn-primary" onClick={syncNow} disabled={!!running} title={authed ? `Last synced ${relative(sync?.lastSyncedAt)}` : 'Sign in to Garmin'}>
        <RefreshCw size={12} className={running ? 'animate-spin' : ''} />
        {running ? 'Syncing…' : sync?.isFirstSync ? 'Initial Sync' : 'Sync Now'}
      </button>
      <button className="btn btn-ghost px-1.5" onClick={onOpenSync} title="Sync settings">
        <Settings2 size={13} />
      </button>
      {authed && (
        <button className="btn btn-ghost px-1.5" onClick={logout} title={`Sign out ${auth?.displayName ?? ''}`}>
          <LogOut size={13} />
        </button>
      )}
    </header>
  );
}
