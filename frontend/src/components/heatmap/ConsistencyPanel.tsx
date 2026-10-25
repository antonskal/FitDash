import { useState } from 'react';
import Panel from '@/components/layout/Panel';
import { useCalendar } from '@/hooks/queries';
import { useDashboard } from '@/store/dashboard';
import { fmtDate } from '@/lib/format';
import ContributionGrid from './ContributionGrid';
import HabitMatrix from './HabitMatrix';

export default function ConsistencyPanel() {
  const { data, isLoading } = useCalendar();
  const activeDate = useDashboard((s) => s.activeDate);
  const [view, setView] = useState<'grid' | 'habits'>('grid');
  const days = data?.days ?? [];
  const end = data?.end ?? activeDate;

  return (
    <Panel
      title="Consistency & Activity Matrix"
      subtitle={`Inspecting ${fmtDate(activeDate, 'ddd, MMM D YYYY')}`}
      loading={isLoading}
      actions={
        <div className="flex gap-0.5 border border-edge-strong rounded-sm p-0.5">
          <button
            className={`h-6 px-2 text-[11px] rounded-[2px] ${view === 'grid' ? 'bg-blue/20 text-blue' : 'text-ink-dim'}`}
            onClick={() => setView('grid')}
          >
            52-week grid
          </button>
          <button
            className={`h-6 px-2 text-[11px] rounded-[2px] ${view === 'habits' ? 'bg-blue/20 text-blue' : 'text-ink-dim'}`}
            onClick={() => setView('habits')}
          >
            Habit matrix
          </button>
        </div>
      }
    >
      {view === 'grid' ? (
        <ContributionGrid days={days} end={end} loading={isLoading} />
      ) : (
        <HabitMatrix days={days} />
      )}
    </Panel>
  );
}
