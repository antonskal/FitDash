import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import type { Activity } from '@/api/types';
import EChart from '@/components/charts/EChart';
import { base, valueAxis } from '@/components/charts/theme';
import { HR_ZONE_COLORS } from '@/lib/colors';
import { hms, pct } from '@/lib/format';

export default function HrZones({ activity }: { activity: Activity }) {
  const zones = activity.hrZones.secondsInZone;
  const bounds = activity.hrZones.lowBoundaries;
  const total = zones.reduce<number>((s, v) => s + (v ?? 0), 0);

  const option = useMemo<EChartsOption>(() => {
    const labels = zones.map((_, i) => {
      const lo = bounds[i];
      const hi = bounds[i + 1];
      const range = lo != null ? (hi != null ? `${lo}–${hi - 1}` : `${lo}+`) : '';
      return `Z${i + 1}${range ? ` ${range}` : ''}`;
    });
    return base({
      grid: { left: 88, right: 72, top: 8, bottom: 20 },
      xAxis: valueAxis({
        axisLabel: { formatter: (v: number) => hms(v) },
      }),
      yAxis: { type: 'category', data: labels, inverse: true, axisLabel: { color: '#9aa0a6', fontSize: 10 }, axisTick: { show: false }, axisLine: { show: false } },
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const it = (params as { value: number; name: string }[])[0];
          return `${it.name}<br/>${hms(it.value)} · ${pct(total ? (it.value / total) * 100 : 0, 1)}`;
        },
      },
      series: [
        {
          type: 'bar',
          data: zones.map((v, i) => ({
            value: v ?? 0,
            itemStyle: { color: HR_ZONE_COLORS[i + 1] ?? HR_ZONE_COLORS[0] },
          })),
          barWidth: 14,
          label: {
            show: true,
            position: 'right',
            color: '#9aa0a6',
            fontSize: 10,
            formatter: (p: { value?: unknown }) => {
              const v = typeof p.value === 'number' ? p.value : 0;
              return `${hms(v)}  ${pct(total ? (v / total) * 100 : 0, 0)}`;
            },
          },
        },
      ],
    });
  }, [zones, bounds, total]);

  const empty = !zones.some((v) => v);

  if (empty) return <div className="text-xs text-ink-faint p-3">No HR zone data</div>;
  return <EChart option={option} height={200} />;
}
