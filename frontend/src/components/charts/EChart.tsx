import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { EChartsOption, ECharts } from 'echarts';

export interface EChartProps {
  option: EChartsOption;
  height?: number | string;
  className?: string;
  /** `echarts.connect` group — all charts sharing a group get linked crosshairs/tooltips. */
  group?: string;
  onEvents?: Record<string, (params: unknown, chart: ECharts) => void>;
  onReady?: (chart: ECharts) => void;
  notMerge?: boolean;
}

const connectedGroups = new Set<string>();

export default function EChart({ option, height = 240, className, group, onEvents, onReady, notMerge = true }: EChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ECharts | null>(null);
  const eventsRef = useRef(onEvents);
  eventsRef.current = onEvents;

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: 'canvas', useDirtyRect: true });
    chartRef.current = chart;
    if (group) {
      chart.group = group;
      if (!connectedGroups.has(group)) {
        connectedGroups.add(group);
      }
      echarts.connect(group);
    }
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    onReady?.(chart);
    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
      if (group) echarts.connect(group);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.setOption(option, { notMerge, lazyUpdate: true });
    if (group) echarts.connect(group);
  }, [option, notMerge, group]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const names = Object.keys(eventsRef.current ?? {});
    const handlers = names.map((name) => {
      const h = (params: unknown) => eventsRef.current?.[name]?.(params, chart);
      chart.on(name, h);
      return [name, h] as const;
    });
    return () => {
      handlers.forEach(([name, h]) => chart.off(name, h));
    };
  }, [onEvents]);

  return <div ref={ref} className={className} style={{ height, width: '100%' }} />;
}
