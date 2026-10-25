import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import EChart from '@/components/charts/EChart';
import { base, categoryAxis, timeAxis, valueAxis } from '@/components/charts/theme';
import StatCard from '@/components/charts/StatCard';
import Panel from '@/components/layout/Panel';
import Row from '@/components/layout/Row';
import { useDaily, useOverview, useSleepDetail } from '@/hooks/queries';
import { C } from '@/lib/colors';
import { fmtTs, hms, num, signed, toTzEpoch } from '@/lib/format';
import { useDashboard } from '@/store/dashboard';

const STAGE_COLOR = [C.blue, C.cyan, C.purple, C.inkFaint];
const STAGE_NAME = ['Deep', 'Light', 'REM', 'Awake'];

export default function SleepRow() {
  const { data: daily, isLoading: dLoad } = useDaily();
  const { data: sleep, isLoading: sLoad } = useSleepDetail();
  const { data: overview } = useOverview();
  const tz = useDashboard((s) => s.timezone);
  const days = daily?.days ?? [];

  const stagesOption = useMemo<EChartsOption>(() => {
    const dates = days.map((d) => d.date);
    return base({
      grid: { left: 48, right: 12, top: 22, bottom: 28 },
      legend: { data: STAGE_NAME, textStyle: { color: C.inkDim, fontSize: 10 }, top: 0, right: 8 },
      xAxis: categoryAxis(dates),
      yAxis: valueAxis({
        name: 'hours',
        axisLabel: { formatter: (v: number) => `${(v / 3600).toFixed(0)}h` },
      }),
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const items = params as { seriesName: string; value: number; axisValue: string; marker: string }[];
          const total = items.reduce((s, it) => s + (it.value || 0), 0);
          return [`${items[0]?.axisValue} · ${hms(total)}`, ...items.map((it) => `${it.marker} ${it.seriesName} ${hms(it.value)}`)].join('<br/>');
        },
      },
      series: [
        { name: 'Deep', type: 'bar', stack: 's', data: days.map((d) => d.deep_s ?? 0), itemStyle: { color: STAGE_COLOR[0] }, barMaxWidth: 16 },
        { name: 'Light', type: 'bar', stack: 's', data: days.map((d) => d.light_s ?? 0), itemStyle: { color: STAGE_COLOR[1] } },
        { name: 'REM', type: 'bar', stack: 's', data: days.map((d) => d.rem_s ?? 0), itemStyle: { color: STAGE_COLOR[2] } },
        { name: 'Awake', type: 'bar', stack: 's', data: days.map((d) => d.awake_s ?? 0), itemStyle: { color: STAGE_COLOR[3] } },
      ],
    });
  }, [days]);

  const regularityOption = useMemo<EChartsOption>(() => {
    const rows = days.filter((d) => d.sleep_start_ts && d.sleep_end_ts);
    const dates = rows.map((d) => d.date);
    const clock = (ms: number) => {
      const t = tz === 'local' ? new Date(ms) : new Date(toTzEpoch(ms, tz));
      const h = t.getHours() + t.getMinutes() / 60;
      return h < 12 ? h + 24 : h;
    };
    const bed = rows.map((d) => clock(d.sleep_start_ts as number));
    const wake = rows.map((d) => clock(d.sleep_end_ts as number));
    return base({
      grid: { left: 48, right: 12, top: 22, bottom: 28 },
      legend: { data: ['Bedtime', 'Wake'], textStyle: { color: C.inkDim, fontSize: 10 }, top: 0, right: 8 },
      xAxis: categoryAxis(dates),
      yAxis: valueAxis({
        min: 18,
        max: 36,
        inverse: false,
        axisLabel: {
          formatter: (v: number) => `${String(Math.floor(v % 24)).padStart(2, '0')}:00`,
        },
      }),
      series: [
        {
          type: 'custom',
          name: 'window',
          renderItem: (_params, api) => {
            const i = Number(api.value(0));
            const a = api.coord([i, Number(api.value(1))]);
            const b = api.coord([i, Number(api.value(2))]);
            const w = ((api.size?.([1, 0]) as number[] | undefined)?.[0] ?? 8) * 0.55;
            return {
              type: 'rect',
              shape: { x: a[0] - w / 2, y: Math.min(a[1], b[1]), width: w, height: Math.abs(b[1] - a[1]) },
              style: { fill: 'rgba(184,119,217,0.35)', stroke: C.purple, lineWidth: 0.5 },
            };
          },
          data: rows.map((d, i) => [i, clock(d.sleep_start_ts as number), clock(d.sleep_end_ts as number)]),
          encode: { x: 0, y: [1, 2] },
        },
        { name: 'Bedtime', type: 'scatter', data: bed, symbolSize: 6, itemStyle: { color: C.purple } },
        { name: 'Wake', type: 'scatter', data: wake, symbolSize: 6, itemStyle: { color: C.yellow } },
      ],
    });
  }, [days, tz]);

  const overnightOption = useMemo<EChartsOption>(() => {
    const map = (s: [number, number][]) => s.map(([t, v]) => [toTzEpoch(t, tz), v]);
    return base({
      grid: { left: 44, right: 44, top: 22, bottom: 24 },
      legend: { data: ['SpO2', 'Respiration', 'Movement'], textStyle: { color: C.inkDim, fontSize: 10 }, top: 0, right: 8 },
      xAxis: timeAxis(),
      yAxis: [
        valueAxis({ name: '%', min: 85, max: 100 }),
        valueAxis({ name: 'brpm / move', splitLine: { show: false } }),
      ],
      series: [
        { name: 'SpO2', type: 'line', data: map(sleep?.spo2 ?? []), showSymbol: false, lineStyle: { color: C.cyan, width: 1.3 }, itemStyle: { color: C.cyan } },
        { name: 'Respiration', type: 'line', yAxisIndex: 1, data: map(sleep?.respiration ?? []), showSymbol: false, lineStyle: { color: C.blue, width: 1.2 }, itemStyle: { color: C.blue } },
        { name: 'Movement', type: 'bar', yAxisIndex: 1, data: map(sleep?.movement ?? []), itemStyle: { color: 'rgba(255,152,48,0.45)' }, barMaxWidth: 3 },
      ],
    });
  }, [sleep, tz]);

  const d = overview?.daily;
  const sess = sleep?.session;

  return (
    <Row id="sleep" title="Sleep Architecture & Routine Regularity">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
        <Panel title="Sleep Stages & Duration" loading={dLoad} empty={!days.some((x) => x.total_sleep_s)} bodyClassName="p-1">
          <EChart option={stagesOption} height={260} />
        </Panel>
        <Panel title="Sleep Regularity" subtitle="Bedtime & wake windows" loading={dLoad} empty={!days.some((x) => x.sleep_start_ts)} bodyClassName="p-1">
          <EChart option={regularityOption} height={260} />
        </Panel>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
        <StatCard label="Avg SpO2" value={num((sess?.avg_spo2 as number | undefined) ?? d?.spo2Avg, 1)} unit="%" color={C.cyan} sub={`Lowest ${num((sess?.lowest_spo2 as number | undefined) ?? d?.spo2Lowest, 0)}%`} />
        <StatCard label="Respiration" value={num((sess?.avg_respiration as number | undefined) ?? d?.respirationAvg, 1)} unit="brpm" color={C.blue} />
        <StatCard label="Sleep Movement" value={num(sess?.avg_movement as number | undefined, 2)} sub={`Restless ${num(sess?.restless_moments as number | undefined, 0)} · awake ${num(sess?.awake_count as number | undefined, 0)}`} />
        <StatCard label="Skin Temp Δ" value={signed((sess?.skin_temp_dev_c as number | undefined) ?? d?.skinTempDevC, 2)} unit="°C" color={C.orange} sub={`${signed((sess?.skin_temp_dev_f as number | undefined) ?? d?.skinTempDevF, 2)} °F`} />
      </div>
      <Panel className="mt-2" title="Overnight Vitals" subtitle={sleep?.session ? `Sleep ${fmtTs(Number(sleep.session.sleep_start_ts), tz)} → ${fmtTs(Number(sleep.session.sleep_end_ts), tz)}` : undefined} loading={sLoad} empty={!sleep?.session} bodyClassName="p-1">
        <EChart option={overnightOption} height={200} />
      </Panel>
    </Row>
  );
}
