import type { EChartsOption } from 'echarts';
import { C } from '@/lib/colors';

export const MONO = '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace';

export const tooltipStyle = {
  backgroundColor: 'rgba(24,27,31,0.96)',
  borderColor: C.edgeStrong,
  borderWidth: 1,
  padding: [6, 10],
  textStyle: { color: C.ink, fontSize: 11, fontFamily: MONO },
  extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.5); border-radius: 2px;',
};

export const axisBase = {
  axisLine: { lineStyle: { color: C.edgeStrong } },
  axisTick: { show: false },
  axisLabel: { color: C.inkDim, fontSize: 10, fontFamily: MONO },
  splitLine: { lineStyle: { color: C.edge, type: 'solid' as const } },
  nameTextStyle: { color: C.inkFaint, fontSize: 10 },
};

export function base(overrides: EChartsOption = {}): EChartsOption {
  return {
    backgroundColor: 'transparent',
    animation: false,
    textStyle: { color: C.ink, fontFamily: 'Inter, system-ui, sans-serif' },
    grid: { left: 44, right: 16, top: 24, bottom: 28, containLabel: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: C.inkFaint, type: 'dashed' }, label: { backgroundColor: C.edgeStrong, color: C.ink, fontFamily: MONO, fontSize: 10 } },
      ...tooltipStyle,
    },
    legend: { textStyle: { color: C.inkDim, fontSize: 10 }, icon: 'roundRect', itemWidth: 10, itemHeight: 3, top: 2, right: 8 },
    ...overrides,
  };
}

export const timeAxis = (extra: Record<string, unknown> = {}) => ({
  type: 'time' as const,
  ...axisBase,
  splitLine: { show: false },
  axisLabel: { ...axisBase.axisLabel, hideOverlap: true },
  ...extra,
});

export const valueAxis = (extra: Record<string, unknown> = {}) => ({
  type: 'value' as const,
  ...axisBase,
  scale: true,
  ...extra,
});

export const categoryAxis = (data: string[], extra: Record<string, unknown> = {}) => ({
  type: 'category' as const,
  data,
  ...axisBase,
  splitLine: { show: false },
  ...extra,
});
