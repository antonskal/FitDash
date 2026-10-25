import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import type { StrengthSummary } from '@/api/types';
import EChart from '@/components/charts/EChart';
import { base, categoryAxis, valueAxis } from '@/components/charts/theme';
import Panel from '@/components/layout/Panel';
import { C } from '@/lib/colors';
import { num, titleCase } from '@/lib/format';

export default function StrengthView({ strength }: { strength: StrengthSummary }) {
  const volumeOption = useMemo<EChartsOption>(() => {
    const cats = strength.perCategory;
    return base({
      grid: { left: 100, right: 16, top: 8, bottom: 24 },
      xAxis: valueAxis({ name: 'kg' }),
      yAxis: categoryAxis(
        cats.map((c) => titleCase(c.category)),
        { inverse: true },
      ),
      series: [{ type: 'bar', data: cats.map((c) => c.volumeKg), itemStyle: { color: C.red }, barWidth: 12 }],
    });
  }, [strength]);

  const e1rmOption = useMemo<EChartsOption>(() => {
    const keys = Object.keys(strength.progression).slice(0, 6);
    const dates = [...new Set(keys.flatMap((k) => strength.progression[k].map((p) => p[0])))].sort();
    return base({
      grid: { left: 48, right: 12, top: 28, bottom: 28 },
      legend: { data: keys.map((k) => k.split(' · ').pop() ?? k), textStyle: { color: C.inkDim, fontSize: 10 }, top: 0 },
      xAxis: categoryAxis(dates),
      yAxis: valueAxis({ name: 'kg' }),
      series: keys.map((k, i) => {
        const by = new Map(strength.progression[k].map((p) => [p[0], p[1]]));
        const colors = [C.red, C.orange, C.yellow, C.cyan, C.blue, C.purple];
        return {
          name: k.split(' · ').pop() ?? k,
          type: 'line' as const,
          data: dates.map((d) => by.get(d) ?? null),
          showSymbol: true,
          symbolSize: 5,
          connectNulls: true,
          lineStyle: { color: colors[i % colors.length] },
          itemStyle: { color: colors[i % colors.length] },
        };
      }),
    });
  }, [strength]);

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 gap-2">
        <div className="panel px-3 py-2">
          <div className="panel-title">Volume</div>
          <div className="text-xl font-mono font-semibold num">{num(strength.totalVolumeKg, 0)} kg</div>
        </div>
        <div className="panel px-3 py-2">
          <div className="panel-title">Sets / Reps</div>
          <div className="text-xl font-mono font-semibold num">
            {strength.totalSets} / {strength.totalReps}
          </div>
        </div>
        <div className="panel px-3 py-2">
          <div className="panel-title">Exercises</div>
          <div className="text-xl font-mono font-semibold num">{strength.perExercise.length}</div>
        </div>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
        <Panel title="Volume by muscle group" bodyClassName="p-1">
          <EChart option={volumeOption} height={200} />
        </Panel>
        <Panel title="Estimated 1RM progression" info="Epley: w × (1 + reps/30)" bodyClassName="p-1">
          <EChart option={e1rmOption} height={200} />
        </Panel>
      </div>
      <Panel title="Set log" bodyClassName="p-0 overflow-auto max-h-72">
        <table className="tbl">
          <thead>
            <tr>
              <th>#</th>
              <th>Type</th>
              <th>Exercise</th>
              <th>Reps</th>
              <th>Weight</th>
              <th>e1RM</th>
            </tr>
          </thead>
          <tbody>
            {strength.sets.map((s) => (
              <tr key={s.index} className={s.type === 'REST' ? 'opacity-40' : ''}>
                <td className="num">{s.index + 1}</td>
                <td>{s.type}</td>
                <td>{s.exercise}</td>
                <td className="num">{s.reps ?? '—'}</td>
                <td className="num">{s.weightKg != null ? `${num(s.weightKg, 1)} kg` : '—'}</td>
                <td className="num">{s.e1rm != null ? `${num(s.e1rm, 1)} kg` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
