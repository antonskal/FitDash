import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import type { Telemetry } from '@/api/types';
import EChart from '@/components/charts/EChart';
import { MONO, axisBase } from '@/components/charts/theme';
import { C } from '@/lib/colors';
import { hms, paceSeconds } from '@/lib/format';

interface Lane {
  key: string;
  name: string;
  color: string;
  unit: string;
  values: (number | null)[];
  invert?: boolean;
}

interface Props {
  telemetry: Telemetry;
  hoverElapsed: number | null;
  onHoverElapsed: (s: number | null) => void;
}

export default function TelemetryChart({ telemetry, hoverElapsed, onHoverElapsed }: Props) {
  const option = useMemo<EChartsOption>(() => {
    const elapsed = telemetry.elapsedS;
    const lanes: Lane[] = [
      { key: 'hr', name: 'Heart Rate', color: C.red, unit: 'bpm', values: telemetry.hr },
      {
        key: 'pace',
        name: 'Pace',
        color: C.orange,
        unit: '/km',
        values: telemetry.speedMps.map((v) => paceSeconds(v)),
        invert: true,
      },
      { key: 'elev', name: 'Elevation', color: C.yellow, unit: 'm', values: telemetry.altitudeM },
      { key: 'cad', name: 'Cadence', color: C.purple, unit: 'spm', values: telemetry.cadence },
      { key: 'pwr', name: 'Power', color: C.cyan, unit: 'W', values: telemetry.power },
      { key: 'tmp', name: 'Temp', color: C.teal, unit: '°C', values: telemetry.temperatureC },
    ].filter((l) => l.values.some((v) => v != null));

    const n = lanes.length || 1;
    const top = 8;
    const gap = 10;
    const laneH = Math.max(52, Math.floor((420 - top - gap * (n - 1)) / n));
    const grids = lanes.map((_, i) => ({
      left: 52,
      right: 16,
      top: top + i * (laneH + gap),
      height: laneH,
    }));
    const xAxes = lanes.map((_, i) => ({
      type: 'value' as const,
      gridIndex: i,
      min: 0,
      max: elapsed[elapsed.length - 1] ?? 0,
      axisLabel: { show: i === n - 1, color: C.inkDim, fontSize: 10, fontFamily: MONO, formatter: (v: number) => hms(v) },
      axisLine: { lineStyle: { color: C.edgeStrong } },
      axisTick: { show: false },
      splitLine: { show: false },
    }));
    const yAxes = lanes.map((l, i) => ({
      type: 'value' as const,
      gridIndex: i,
      scale: true,
      inverse: !!l.invert,
      name: l.name,
      nameLocation: 'end' as const,
      ...axisBase,
      nameTextStyle: { color: C.inkFaint, fontSize: 10, align: 'left' as const, padding: [0, 0, 0, 0] },
      splitNumber: 2,
      splitLine: { lineStyle: { color: C.edge } },
    }));
    const series = lanes.map((l, i) => ({
      name: l.name,
      type: 'line' as const,
      xAxisIndex: i,
      yAxisIndex: i,
      showSymbol: false,
      data: elapsed.map((t, idx) => [t, l.values[idx]]),
      lineStyle: { width: 1.3, color: l.color },
      itemStyle: { color: l.color },
      areaStyle: l.key === 'elev' ? { color: 'rgba(250,222,42,0.12)' } : undefined,
    }));

    const mark = hoverElapsed;
    return {
      backgroundColor: 'transparent',
      animation: false,
      axisPointer: {
        link: [{ xAxisIndex: 'all' }],
        label: { backgroundColor: C.edgeStrong, fontFamily: MONO, fontSize: 10 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: C.inkFaint, type: 'dashed' } },
        backgroundColor: 'rgba(24,27,31,0.96)',
        borderColor: C.edgeStrong,
        textStyle: { color: C.ink, fontSize: 11, fontFamily: MONO },
        formatter: (params: unknown) => {
          const items = params as { seriesName: string; value: [number, number | null]; marker: string }[];
          const t = items[0]?.value?.[0] ?? 0;
          const lines = [`<b>${hms(t)}</b>`];
          for (const it of items) {
            const v = it.value?.[1];
            const lane = lanes.find((l) => l.name === it.seriesName);
            let txt = v == null ? '—' : v.toFixed(lane?.key === 'pace' ? 0 : 0);
            if (lane?.key === 'pace' && v != null) {
              const m = Math.floor(v / 60);
              const s = Math.round(v % 60);
              txt = `${m}:${String(s).padStart(2, '0')}`;
            }
            lines.push(`${it.marker} ${it.seriesName} ${txt} ${lane?.unit ?? ''}`);
          }
          return lines.join('<br/>');
        },
      },
      grid: grids,
      xAxis: xAxes,
      yAxis: yAxes,
      series: series.map((s) =>
        mark == null
          ? s
          : {
              ...s,
              markLine: {
                silent: true,
                symbol: 'none',
                data: [{ xAxis: mark }],
                lineStyle: { color: C.cyan, type: 'dashed', width: 1 },
                label: { show: false },
              },
            },
      ),
    };
  }, [telemetry, hoverElapsed]);

  return (
    <EChart
      option={option}
      height={420}
      onEvents={{
        updateAxisPointer: (params) => {
          const p = params as { axesInfo?: { value?: number }[] };
          const v = p.axesInfo?.[0]?.value;
          onHoverElapsed(typeof v === 'number' ? v : null);
        },
        globalout: () => onHoverElapsed(null),
      }}
    />
  );
}
