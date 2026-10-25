import type { SyncLive } from '@/api/types';
import { relative } from '@/lib/format';

interface Props {
  live: SyncLive | null;
  lastSyncedAt: string | null;
  onClick?: () => void;
}

export default function SyncStatusBadge({ live, lastSyncedAt, onClick }: Props) {
  const running = live?.status === 'running';
  const error = live?.status === 'error';
  const color = running ? 'bg-blue' : error ? 'bg-red' : lastSyncedAt ? 'bg-emerald' : 'bg-ink-faint';
  const label = running
    ? `${live?.phase === 'activities' ? `Activities ${live.activitiesDone}/${live.activitiesNew}` : `${live?.daysDone ?? 0}/${live?.daysTotal ?? 0} days`}`
    : error
      ? 'Sync error'
      : `Last synced: ${relative(lastSyncedAt)}`;
  return (
    <button
      onClick={onClick}
      className="hidden md:flex items-center gap-1.5 h-7 px-2 rounded-sm border border-edge-strong bg-panel text-[11px] text-ink-dim hover:text-ink hover:border-ink-faint"
      title={live?.message || label}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${color} ${running ? 'pulse' : ''}`} />
      <span className="num">{label}</span>
    </button>
  );
}
