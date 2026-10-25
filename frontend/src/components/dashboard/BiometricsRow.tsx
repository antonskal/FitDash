import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import EChart from '@/components/charts/EChart';
import { base, timeAxis, valueAxis } from '@/components/charts/theme';
import Panel from '@/components/layout/Panel';
import Row from '@/components/layout/Row';
import { useDaily, useIntraday, useOverview } from '@/hooks/queries';
import { C } from '@/lib/colors';
import { toTzEpoch } from '@/lib/format';
import { useDashboard } from '@/store/dashboard';

export default function BiometricsRow() {
  const { data: intra, isLoading } = useIntraday();
  const { data: daily } = useDaily();
  const { data: overview } = useOverview();
  const tz = useDashboard((s) => s.timezone);
  const rhr = overview?.readiness.restingHr7d ?? overview?.readiness.restingHr ?? null;

  const shift = (series: [number, number][]) => series.map(([t, v]) => [toTzEpoch(t, tz), v] as [number, number]);

  const hrOption = useMemo<EChartsOption>(() => {
    const hr = shift(intra?.hr ?? []);
    return base({
      grid: { left: 44, right: 12, top: 22, bottom: 24 },
      xAxis: timeAxis(),
      yAxis: valueAxis({ name: 'bpm', min: (m: number) => Math.max(30, Math.floor(m - 8)), max: (m: number) => Math.ceil(m + 8) }),
      series: [
        {
          name: 'Heart Rate',
          type: 'line',
          data: hr,
          showSymbol: false,
          lineStyle: { width: 1.4, color: C.red },
          areaStyle: { color: 'rgba(242,73,92,0.12)' },
          markLine:
            rhr != null
              ? {
                  silent: true,
                  symbol: 'none',
                  data: [{ yAxis: rhr, name: '7d RHR' }],
                  label: { formatter: '7d RHR {c}', color: C.cyan, fontSize: 10 },
                  lineStyle: { color: C.cyan, type: 'dashed', width: 1 },
                }
              : undefined,
        },
      ],
    });
  }, [intra, tz, rhr]);

  const rhrOption = useMemo<EChartsOption>(() => {
    const pts = (daily?.days ?? [])
      .filter((d) => d.resting_hr != null)
      .map((d) => [d.date, d.resting_hr] as [string, number]);
    return base({
      grid: { left: 44, right: 12, top: 8, bottom: 20 },
      xAxis: { type: 'category', data: pts.map((p) => p[0]), axisLabel: { color: C.inkDim, fontSize: 9 }, axisTick: { show: false }, axisLine: { lineStyle: { color: C.edgeStrong } } },
      yAxis: valueAxis({ scale: true, splitNumber: 3 }),
      series: [{ type: 'line', data: pts.map((p) => p[1]), showSymbol: pts.length < 14, symbolSize: 4, lineStyle: { color: C.orange, width: 1.5 }, itemStyle: { color: C.orange } }],
      tooltip: { trigger: 'axis' },
    });
  }, [daily]);

  const stressOption = useMemo<EChartsOption>(() => {
    const stress = shift(intra?.stress ?? []);
    const bb = shift(intra?.bodyBattery ?? []);
    return base({
      grid: { left: 44, right: 44, top: 22, bottom: 24 },
      xAxis: timeAxis(),
      yAxis: [
        valueAxis({ name: 'Stress', min: 0, max: 100 }),
        valueAxis({ name: 'Body Battery', min: 0, max: 100, splitLine: { show: false } }),
      ],
      visualMap: {
        show: false,
        seriesIndex: 0,
        pieces: [
          { lte: 24, color: C.blue },
          { gt: 24, lte: 49, color: C.yellow },
          { gt: 49, lte: 74, color: C.orange },
          { gt: 74, color: C.red },
        ],
      },
      legend: { data: ['Stress', 'Body Battery'], textStyle: { color: C.inkDim, fontSize: 10 }, top: 0, right: 8 },
      series: [
        {
          name: 'Stress',
          type: 'line',
          data: stress,
          showSymbol: false,
          lineStyle: { width: 1 },
          areaStyle: { opacity: 0.28 },
        },
        {
          name: 'Body Battery',
          type: 'line',
          yAxisIndex: 1,
          data: bb,
          showSymbol: false,
          lineStyle: { width: 1.6, color: C.green },
          itemStyle: { color: C.green },
        },
      ],
    });
  }, [intra, tz]);

  return (
    <Row id="biometrics" title="Intraday Biometrics" hint="Linked crosshairs · hover any chart">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
        <Panel title="Heart Rate" subtitle="1–3 min resolution" loading={isLoading} empty={!intra?.hr.length} bodyClassName="p-1">
          <EChart option={hrOption} height={220} group="intraday" />
          <div className="px-2 pt-1 panel-title">Daily resting HR</div>
          <EChart option={rhrOption} height={88} />
        </Panel>
        <Panel
          title="Stress & Body Battery"
          subtitle="Rest · Low · Medium · High"
          info="Stress is unmeasurable during activities (Garmin reports −1)."
          loading={isLoading}
          empty={!intra?.stress.length && !intra?.bodyBattery.length}
          bodyClassName="p-1"
        >
          <EChart option={stressOption} height={320} group="intraday" />
          <div className="flex justify-center gap-3 text-[10px] text-ink-faint pb-1">
            <span className="flex items-center gap-1">
              <i className="w-2 h-2 rounded-sm" style={{ background: C.blue }} /> Rest
            </span>
            <span className="flex items-center gap-1">
              <i className="w-2 h-2 rounded-sm" style={{ background: C.yellow }} /> Low
            </span>
            <span className="flex items-center gap-1">
              <i className="w-2 h-2 rounded-sm" style={{ background: C.orange }} /> Medium
            </span>
            <span className="flex items-center gap-1">
              <i className="w-2 h-2 rounded-sm" style={{ background: C.red }} /> High
            </span>
          </div>
        </Panel>
      </div>
    </Row>
  );
}
