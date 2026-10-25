import { useMemo, useState } from 'react';
import Panel from '@/components/layout/Panel';
import Row from '@/components/layout/Row';
import SportBadge from '@/components/common/SportBadge';
import ActivityInspector from '@/components/activity/ActivityInspector';
import { useActivities } from '@/hooks/queries';
import { useDashboard } from '@/store/dashboard';
import { SPORT_LABEL } from '@/lib/colors';
import { hms, km, num, pace, speedKmh } from '@/lib/format';
import type { SportCategory } from '@/api/types';

const CATS: (SportCategory | 'all')[] = ['all', 'running', 'cycling', 'swimming', 'strength', 'yoga', 'walking', 'hiking', 'cardio', 'other'];

export default function WorkoutsRow() {
  const [cat, setCat] = useState<SportCategory | 'all'>('all');
  const [q, setQ] = useState('');
  const { data, isLoading } = useActivities(cat === 'all' ? undefined : cat, q || undefined);
  const selected = useDashboard((s) => s.selectedActivityId);
  const select = useDashboard((s) => s.selectActivity);
  const activities = data?.activities ?? [];

  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of data?.categories ?? []) m.set(c.category, c.count);
    return m;
  }, [data]);

  return (
    <Row id="workouts" title="Workouts, GPS Telemetry & Strength Log" hint={`${activities.length} activities`}>
      <Panel
        title="Activity Timeline"
        loading={isLoading}
        empty={!activities.length}
        emptyText="No workouts in this window"
        actions={
          <input
            className="input h-7 w-44 text-xs"
            placeholder="Search title or place…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        }
        bodyClassName="p-0"
      >
        <div className="flex flex-wrap gap-1 px-2 py-2 border-b border-edge">
          {CATS.map((c) => (
            <button key={c} className={`pill ${cat === c ? 'pill-active' : ''}`} onClick={() => setCat(c)}>
              {c === 'all' ? 'All' : SPORT_LABEL[c]}
              {c !== 'all' && counts.get(c) ? <span className="num ml-1 text-ink-faint">{counts.get(c)}</span> : null}
            </button>
          ))}
        </div>
        <div className="overflow-auto max-h-[420px]">
          <table className="tbl">
            <thead className="sticky top-0 bg-panel z-10">
              <tr>
                <th>Date</th>
                <th>Sport</th>
                <th>Title</th>
                <th>Duration</th>
                <th>Distance</th>
                <th>Pace / Speed</th>
                <th>Avg / Max HR</th>
                <th>Elev</th>
                <th>TE A/An</th>
                <th>Load</th>
              </tr>
            </thead>
            <tbody>
              {activities.map((a) => (
                <tr
                  key={a.id}
                  className={`cursor-pointer ${selected === a.id ? 'bg-blue/10' : ''}`}
                  onClick={() => select(selected === a.id ? null : a.id)}
                >
                  <td className="num">{a.date}</td>
                  <td>
                    <SportBadge category={a.category} type={a.type} />
                  </td>
                  <td className="max-w-[180px] truncate">{a.name || a.type}</td>
                  <td className="num">{hms(a.durationS)}</td>
                  <td className="num">{km(a.distanceM)}</td>
                  <td className="num">{a.category === 'cycling' ? speedKmh(a.avgSpeedMps) : pace(a.avgSpeedMps)}</td>
                  <td className="num">
                    {num(a.avgHr)} / {num(a.maxHr)}
                  </td>
                  <td className="num">{a.elevationGainM != null ? `+${num(a.elevationGainM, 0)} m` : '—'}</td>
                  <td className="num">
                    {num(a.aerobicTe, 1)} / {num(a.anaerobicTe, 1)}
                  </td>
                  <td className="num">{num(a.trainingLoad, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <ActivityInspector />
    </Row>
  );
}
