import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { CalendarDay } from '@/api/types';
import { C } from '@/lib/colors';
import { addDays, dayjs, pct, todayStr } from '@/lib/format';
import { HABITS, completionRate, habitDone, streakStats, type HabitId } from '@/lib/heatmap';
import { useDashboard } from '@/store/dashboard';
import { useSettings } from '@/hooks/queries';

interface Props {
  days: CalendarDay[];
}

export default function HabitMatrix({ days }: Props) {
  const activeDate = useDashboard((s) => s.activeDate);
  const setActiveDate = useDashboard((s) => s.setActiveDate);
  const { data: settings } = useSettings();
  const sleepTh = settings?.sleepScoreHabitThreshold ?? 80;
  const [month, setMonth] = useState(activeDate.slice(0, 7));

  useEffect(() => {
    setMonth(activeDate.slice(0, 7));
  }, [activeDate]);

  const monthStart = `${month}-01`;
  const dim = dayjs(monthStart);
  const daysInMonth = dim.daysInMonth();
  const asOf = month === todayStr().slice(0, 7) ? todayStr() : dim.endOf('month').format('YYYY-MM-DD');

  const byDate = useMemo(() => new Map(days.map((d) => [d.date, d])), [days]);
  const cols = useMemo(
    () => Array.from({ length: daysInMonth }, (_, i) => addDays(monthStart, i)),
    [daysInMonth, monthStart],
  );

  const shift = (n: number) => setMonth(dim.add(n, 'month').format('YYYY-MM'));

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1">
          <button className="btn btn-ghost px-1.5" onClick={() => shift(-1)} aria-label="Previous month">
            <ChevronLeft size={14} />
          </button>
          <span className="text-xs font-medium w-28 text-center">{dim.format('MMMM YYYY')}</span>
          <button className="btn btn-ghost px-1.5" onClick={() => shift(1)} aria-label="Next month">
            <ChevronRight size={14} />
          </button>
        </div>
        <span className="text-[10px] text-ink-faint">Streak · best · 7d / 30d</span>
      </div>

      <div className="overflow-x-auto">
        <table className="text-[10px] border-separate border-spacing-[2px] w-full">
          <thead>
            <tr>
              <th className="w-24 sticky left-0 bg-panel z-10" />
              {cols.map((d) => (
                <th
                  key={d}
                  className={`w-[14px] min-w-[14px] font-normal text-ink-faint num ${d === activeDate ? 'text-ink' : ''}`}
                >
                  {dayjs(d).format('D')}
                </th>
              ))}
              <th className="pl-2 text-left font-normal text-ink-faint w-32 sticky right-0 bg-panel"> </th>
            </tr>
          </thead>
          <tbody>
            {HABITS.map((h) => {
              const streaks = streakStats(days, h.id, asOf, sleepTh);
              const r7 = completionRate(days, h.id, asOf, 7, sleepTh);
              const r30 = completionRate(days, h.id, asOf, 30, sleepTh);
              return (
                <tr key={h.id}>
                  <td className="text-ink-dim pr-1 whitespace-nowrap text-right sticky left-0 bg-panel z-10">{h.label}</td>
                  {cols.map((d) => {
                    const day = byDate.get(d);
                    const future = d > todayStr();
                    const done = !future && !!day && habitDone(day, h.id as HabitId, sleepTh);
                    const selected = d === activeDate;
                    return (
                      <td key={d} className="p-0">
                        <button
                          type="button"
                          disabled={future || !day}
                          onClick={() => day && setActiveDate(d)}
                          className={`cell block w-[14px] h-[14px] mx-auto ${selected ? 'ring-1 ring-white/70' : ''}`}
                          style={{
                            background: future ? 'transparent' : done ? C.green : '#1c2128',
                            opacity: day ? 1 : 0.35,
                          }}
                          aria-label={`${h.label} ${d}`}
                        />
                      </td>
                    );
                  })}
                  <td className="pl-2 text-ink-dim num whitespace-nowrap sticky right-0 bg-panel">
                    <span className="text-ink">{streaks.current}</span>
                    <span className="text-ink-faint"> · {streaks.best}</span>
                    <span className="ml-2">{pct(r7 * 100)}</span>
                    <span className="text-ink-faint"> / {pct(r30 * 100)}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
