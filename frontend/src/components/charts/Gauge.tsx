import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import EChart from './EChart';
import { MONO } from './theme';
import { C } from '@/lib/colors';

interface GaugeProps {
  label: string;
  value: number | null | undefined;
  min?: number;
  max?: number;
  unit?: string;
  /** threshold stops as [fraction, color] like Grafana */
  thresholds?: [number, string][];
  sub?: string;
  height?: number;
}

const DEFAULT_THRESHOLDS: [number, string][] = [
  [0.6, C.red],
  [0.8, C.yellow],
  [1, C.green],
];

export default function Gauge({ label, value, min = 0, max = 100, unit = '', thresholds = DEFAULT_THRESHOLDS, sub, height = 150 }: GaugeProps) {
  const option = useMemo<EChartsOption>(() => {
    const v = value ?? null;
    const frac = v === null ? 0 : (v - min) / (max - min);
    const color = v === null ? C.inkFaint : (thresholds.find(([f]) => frac <= f)?.[1] ?? thresholds[thresholds.length - 1][1]);
    return {
      backgroundColor: 'transparent',
      animation: false,
      series: [
        {
          type: 'gauge',
          startAngle: 210,
          endAngle: -30,
          min,
          max,
          radius: '100%',
          center: ['50%', '62%'],
          progress: { show: true, width: 10, roundCap: false, itemStyle: { color } },
          axisLine: { lineStyle: { width: 10, color: [[1, C.edge]] } },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false },
          pointer: { show: false },
          anchor: { show: false },
          title: { show: false },
          detail: {
            valueAnimation: false,
            offsetCenter: [0, '-5%'],
            formatter: (val: number) => (v === null ? '—' : `${Math.round(val)}`),
            color,
            fontSize: 26,
            fontWeight: 600,
            fontFamily: MONO,
          },
          data: [{ value: v ?? 0 }],
        },
        {
          // threshold arc (thin outer ring)
          type: 'gauge',
          startAngle: 210,
          endAngle: -30,
          min,
          max,
          radius: '100%',
          center: ['50%', '62%'],
          axisLine: {
            lineStyle: {
              width: 2,
              color: thresholds.map(([f, c]) => [f, c]) as [number, string][],
            },
          },
          splitLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          pointer: { show: false },
          detail: { show: false },
          data: [],
        },
      ],
    };
  }, [value, min, max, thresholds]);

  return (
    <div className="panel px-2 pt-2 pb-1 flex flex-col min-w-0">
      <div className="panel-title truncate px-1">{label}</div>
      <EChart option={option} height={height - 36} />
      <div className="text-center text-[10px] text-ink-faint -mt-3 num h-4 truncate">{sub ?? (unit ? unit : '')}</div>
    </div>
  );
}
