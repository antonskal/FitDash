import { useState } from 'react';
import { X } from 'lucide-react';
import { useActivityDetail } from '@/hooks/queries';
import { useDashboard } from '@/store/dashboard';
import Panel from '@/components/layout/Panel';
import SportBadge from '@/components/common/SportBadge';
import { hms, km, num, pace, speedKmh } from '@/lib/format';
import GpsMap from './GpsMap';
import TelemetryChart from './TelemetryChart';
import HrZones from './HrZones';
import StrengthView from './StrengthView';

export default function ActivityInspector() {
  const id = useDashboard((s) => s.selectedActivityId);
  const select = useDashboard((s) => s.selectActivity);
  const { data, isLoading } = useActivityDetail(id);
  const [hover, setHover] = useState<number | null>(null);

  if (id == null) return null;
  const a = data?.summary;

  return (
    <div className="mt-2 space-y-2">
      <Panel
        title={a ? a.name || a.type || 'Activity' : 'Workout inspector'}
        subtitle={a ? `${a.date} · ${hms(a.durationS)} · ${km(a.distanceM)}` : undefined}
        loading={isLoading}
        actions={
          <button className="btn btn-ghost px-1.5" onClick={() => select(null)} aria-label="Close inspector">
            <X size={14} />
          </button>
        }
      >
        {a && (
          <div className="flex flex-wrap items-center gap-3 text-xs text-ink-dim px-1">
            <SportBadge category={a.category} type={a.type} />
            <span className="num">Avg HR {num(a.avgHr)} / max {num(a.maxHr)}</span>
            <span className="num">{a.category === 'cycling' ? speedKmh(a.avgSpeedMps) : pace(a.avgSpeedMps)}</span>
            <span className="num">+{num(a.elevationGainM, 0)} m</span>
            <span className="num">TE {num(a.aerobicTe, 1)} / {num(a.anaerobicTe, 1)}</span>
            {a.location && <span>{a.location}</span>}
          </div>
        )}
      </Panel>

      {data && (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
            <Panel title="GPS Route" subtitle="Colored by selected metric" bodyClassName="p-0">
              <GpsMap telemetry={data.telemetry} hoverElapsed={hover} onHoverElapsed={setHover} />
            </Panel>
            <Panel title="Heart Rate Zones" bodyClassName="p-1">
              <HrZones activity={data.summary} />
            </Panel>
          </div>
          <Panel title="Activity Duration Timeline" subtitle="Elapsed time · hover syncs with the map" bodyClassName="p-1">
            <TelemetryChart telemetry={data.telemetry} hoverElapsed={hover} onHoverElapsed={setHover} />
          </Panel>
          {data.strength && (
            <Panel title="Strength Training" bodyClassName="p-2">
              <StrengthView strength={data.strength} />
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
