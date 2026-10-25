import { ChevronLeft, ChevronRight } from 'lucide-react';
import ConsistencyPanel from '@/components/heatmap/ConsistencyPanel';
import VitalsRow from '@/components/dashboard/VitalsRow';
import BiometricsRow from '@/components/dashboard/BiometricsRow';
import StepsRow from '@/components/dashboard/StepsRow';
import SleepRow from '@/components/dashboard/SleepRow';
import WorkoutsRow from '@/components/dashboard/WorkoutsRow';
import { useSettings } from '@/hooks/queries';
import { useDashboard } from '@/store/dashboard';
import { addDays, fmtDate, todayStr } from '@/lib/format';

interface Props {
  onOpenSync: () => void;
}

export default function Dashboard({ onOpenSync }: Props) {
  const { data: settings } = useSettings();
  const activeDate = useDashboard((s) => s.activeDate);
  const setActiveDate = useDashboard((s) => s.setActiveDate);
  const empty = (settings?.bounds.days ?? 0) === 0 && settings !== undefined;

  return (
    <main className="flex-1 px-3 py-3 max-w-[1680px] mx-auto w-full">
      <div className="flex items-center gap-2 mb-3">
        <button className="btn btn-ghost px-1.5" onClick={() => setActiveDate(addDays(activeDate, -1))} aria-label="Previous day">
          <ChevronLeft size={14} />
        </button>
        <div className="text-sm font-medium">{fmtDate(activeDate, 'dddd, MMMM D YYYY')}</div>
        <button
          className="btn btn-ghost px-1.5"
          onClick={() => setActiveDate(addDays(activeDate, 1))}
          disabled={activeDate >= todayStr()}
          aria-label="Next day"
        >
          <ChevronRight size={14} />
        </button>
        {activeDate !== todayStr() && (
          <button className="btn h-7" onClick={() => setActiveDate(todayStr())}>
            Today
          </button>
        )}
        <div className="flex-1" />
        {settings?.bounds.firstDate && (
          <span className="text-[11px] text-ink-faint num">
            Library {settings.bounds.firstDate} → {settings.bounds.lastDate} · {settings.bounds.days} days · {settings.bounds.activities} workouts
          </span>
        )}
      </div>

      {empty ? (
        <div className="panel p-10 text-center">
          <h2 className="text-lg font-semibold mb-2">No telemetry yet</h2>
          <p className="text-sm text-ink-dim mb-4 max-w-md mx-auto">
            Sign in to Garmin Connect to run an initial backfill, or start the API with <code className="text-ink-faint">python run.py --demo</code> to
            explore the dashboard offline.
          </p>
          <button className="btn btn-primary" onClick={onOpenSync}>
            Connect Garmin
          </button>
        </div>
      ) : (
        <>
          <div className="mb-3">
            <ConsistencyPanel />
          </div>
          <VitalsRow />
          <BiometricsRow />
          <StepsRow />
          <SleepRow />
          <WorkoutsRow />
        </>
      )}
    </main>
  );
}
