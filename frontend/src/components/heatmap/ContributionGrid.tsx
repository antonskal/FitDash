import { useMemo, useState } from 'react';
import type { CalendarDay } from '@/api/types';
import { PALETTES, type PaletteName } from '@/lib/colors';
import { dayjs } from '@/lib/format';
import {
  FILTERS,
  INTENSITIES,
  buildWeeks,
  cellValue,
  dayTooltip,
  intensityLevel,
  quantileThresholds,
  type HeatFilter,
  type Intensity,
} from '@/lib/heatmap';
import { useDashboard } from '@/store/dashboard';

interface Props {
  days: CalendarDay[];
  end: string;
  loading?: boolean;
}

const DOW = ['Mon', '', 'Wed', '', 'Fri', '', 'Sun'];

export default function ContributionGrid({ days, end, loading }: Props) {
  const setActiveDate = useDashboard((s) => s.setActiveDate);
  const activeDate = useDashboard((s) => s.activeDate);
  const [filter, setFilter] = useState<HeatFilter>('all');
  const [intensity, setIntensity] = useState<Intensity>('duration');
  const [palette, setPalette] = useState<PaletteName>('emerald');
  const [tip, setTip] = useState<{ x: number; y: number; date: string } | null>(null);

  const byDate = useMemo(() => new Map(days.map((d) => [d.date, d])), [days]);
  const weeks = useMemo(() => buildWeeks(end, 52), [end]);
  const effectiveIntensity: Intensity = filter === 'steps' ? 'steps' : intensity;

  const thresholds = useMemo(() => {
    const values = days.map((d) => cellValue(d, filter, effectiveIntensity));
    return quantileThresholds(values);
  }, [days, filter, effectiveIntensity]);

  const colors = PALETTES[palette];
  const empty = days.length === 0;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5 mb-2">
        {FILTERS.map((f) => (
          <button key={f.id} className={`pill ${filter === f.id ? 'pill-active' : ''}`} onClick={() => setFilter(f.id)}>
            {f.label}
          </button>
        ))}
        <span className="mx-1 w-px h-4 bg-edge" />
        {INTENSITIES.filter((i) => filter !== 'steps' || i.id === 'steps').map((i) => (
          <button
            key={i.id}
            className={`pill ${effectiveIntensity === i.id ? 'pill-active' : ''}`}
            onClick={() => setIntensity(i.id)}
          >
            {i.label}
          </button>
        ))}
        <span className="mx-1 w-px h-4 bg-edge" />
        {(['emerald', 'cyan'] as PaletteName[]).map((p) => (
          <button key={p} className={`pill ${palette === p ? 'pill-active' : ''}`} onClick={() => setPalette(p)}>
            {p === 'emerald' ? 'Emerald' : 'Cyan'}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto pb-1" onMouseLeave={() => setTip(null)}>
        <div className="inline-flex gap-2 min-w-max">
          <div className="flex flex-col justify-between text-[9px] text-ink-faint pt-3 h-[calc(7*11px+6*3px+12px)] w-6">
            {DOW.map((d, i) => (
              <span key={i} className="h-[11px] leading-[11px]">
                {d}
              </span>
            ))}
          </div>
          <div>
            <div className="flex gap-[3px] mb-0.5 h-3">
              {weeks.map((week, i) => {
                const first = week.find((d) => d.endsWith('-01'));
                return (
                  <div key={i} className="w-[11px] min-w-[11px] shrink-0 text-[9px] text-ink-faint leading-3 overflow-visible">
                    {first ? dayjs(first).format('MMM') : ''}
                  </div>
                );
              })}
            </div>
            <div className="flex gap-[3px]">
              {weeks.map((week, wi) => (
                <div key={wi} className="flex flex-col gap-[3px] w-[11px] min-w-[11px] shrink-0">
                  {week.map((date) => {
                    const day = byDate.get(date);
                    const future = date > end;
                    const value = day && !future ? cellValue(day, filter, effectiveIntensity) : 0;
                    const level = future || !day ? 0 : intensityLevel(value, thresholds);
                    const selected = date === activeDate;
                    return (
                      <button
                        key={date}
                        type="button"
                        disabled={future || !day}
                        className={`cell w-[11px] h-[11px] ${selected ? 'ring-1 ring-white/80' : ''}`}
                        style={{ background: future ? 'transparent' : colors[level], opacity: day ? 1 : 0.35 }}
                        onClick={() => day && setActiveDate(date)}
                        onMouseEnter={(e) => day && setTip({ x: e.clientX, y: e.clientY, date })}
                        onMouseMove={(e) => day && setTip({ x: e.clientX, y: e.clientY, date })}
                        aria-label={date}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-end gap-1 text-[10px] text-ink-faint">
        <span>Less</span>
        {colors.map((c, i) => (
          <span key={i} className="w-[11px] h-[11px] rounded-[2px]" style={{ background: c }} />
        ))}
        <span>More</span>
      </div>

      {tip && byDate.get(tip.date) && (
        <div
          className="pointer-events-none fixed z-40 panel px-2.5 py-1.5 text-[11px] max-w-xs"
          style={{ left: tip.x + 12, top: tip.y + 12 }}
        >
          {(() => {
            const t = dayTooltip(byDate.get(tip.date)!, filter);
            return (
              <>
                <div className="font-medium text-ink mb-0.5">{t.title}</div>
                {t.lines.map((l) => (
                  <div key={l} className="text-ink-dim num">
                    {l}
                  </div>
                ))}
              </>
            );
          })()}
        </div>
      )}
      {empty && !loading && <p className="text-xs text-ink-faint mt-2">No calendar data yet — run a sync.</p>}
    </div>
  );
}
