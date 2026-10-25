import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import EChart from '@/components/charts/EChart';
import { axisBase, base, categoryAxis, valueAxis } from '@/components/charts/theme';
import Panel from '@/components/layout/Panel';
import Row from '@/components/layout/Row';
import { useDaily, useHourlySteps, useSettings } from '@/hooks/queries';
import { C } from '@/lib/colors';

export default function StepsRow() {
  const { data: hourly, isLoading: hLoad } = useHourlySteps();
  const { data: daily, isLoading: dLoad } = useDaily();
  const { data: settings } = useSettings();
  const intensityTarget = settings?.weeklyIntensityTargetMin ?? 150;

  const heatOption = useMemo<EChartsOption>(() => {
    const cells = hourly?.cells ?? [];
    const dates = [...new Set(cells.map((c) => c.date))];
    const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0') + ':00');
    const dateIndex = new Map(dates.map((d, i) => [d, i]));
    const data = cells.map((c) => [dateIndex.get(c.date) ?? 0, c.hour, c.steps]);
    const max = Math.max(1, ...cells.map((c) => c.steps));
    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        formatter: (p: unknown) => {
          const v = p as { value: number[] };
          const date = dates[v.value[0]] ?? '';
          return `${date} ${hours[v.value[1]]}<br/>${v.value[2].toLocaleString()} steps`;
        },
      },
      grid: { left: 48, right: 16, top: 8, bottom: 40, containLabel: false },
      xAxis: { type: 'category', data: dates, ...axisBase, axisLabel: { ...axisBase.axisLabel, rotate: dates.length > 21 ? 45 : 0 } },
      yAxis: { type: 'category', data: hours, ...axisBase, inverse: true, splitLine: { show: false } },
      visualMap: {
        min: 0,
        max,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        text: ['More', 'Less'],
        textStyle: { color: C.inkFaint, fontSize: 10 },
        inRange: { color: ['#1c2128', '#0e4429', '#006d32', '#26a641', '#39d353'] },
      },
      series: [{ type: 'heatmap', data, emphasis: { itemStyle: { borderColor: '#fff', borderWidth: 1 } } }],
    };
  }, [hourly]);

  const barsOption = useMemo<EChartsOption>(() => {
    const days = daily?.days ?? [];
    const dates = days.map((d) => d.date);
    return base({
      grid: { left: 48, right: 44, top: 24, bottom: 28 },
      legend: { data: ['Steps', 'Moderate', 'Vigorous'], textStyle: { color: C.inkDim, fontSize: 10 }, top: 0, right: 8 },
      xAxis: categoryAxis(dates),
      yAxis: [
        valueAxis({ name: 'steps' }),
        valueAxis({ name: 'min', splitLine: { show: false } }),
      ],
      series: [
        { name: 'Steps', type: 'bar', data: days.map((d) => d.total_steps), itemStyle: { color: C.green }, barMaxWidth: 14 },
        { name: 'Moderate', type: 'bar', yAxisIndex: 1, stack: 'int', data: days.map((d) => d.moderate_intensity_min), itemStyle: { color: C.yellow }, barMaxWidth: 10 },
        { name: 'Vigorous', type: 'bar', yAxisIndex: 1, stack: 'int', data: days.map((d) => d.vigorous_intensity_min), itemStyle: { color: C.orange }, barMaxWidth: 10 },
      ],
    });
  }, [daily]);

  const weekMin = (daily?.days ?? []).reduce(
    (s, d) => s + (d.moderate_intensity_min ?? 0) + (d.vigorous_intensity_min ?? 0),
    0,
  );

  return (
    <Row
      id="steps"
      title="Steps & Activity Intensity"
      hint={`Window intensity ${weekMin} min · weekly target ${intensityTarget} min`}
    >
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
        <Panel title="Hourly Steps Heatmap" subtitle="Local hour of day" loading={hLoad} empty={!hourly?.cells.length} bodyClassName="p-1">
          <EChart option={heatOption} height={320} />
        </Panel>
        <Panel title="Daily Steps & Intensity Minutes" loading={dLoad} empty={!daily?.days.length} bodyClassName="p-1">
          <EChart option={barsOption} height={320} />
        </Panel>
      </div>
    </Row>
  );
}
