import type { ReactNode } from 'react';
import { C } from '@/lib/colors';

interface StatCardProps {
  label: string;
  value: ReactNode;
  unit?: string;
  sub?: ReactNode;
  color?: string;
  /** 0..1 progress bar underneath */
  progress?: number | null;
  progressColor?: string;
  spark?: number[];
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export default function StatCard({ label, value, unit, sub, color = C.ink, progress, progressColor = C.green, spark, className = '', size = 'md' }: StatCardProps) {
  const valueCls = size === 'lg' ? 'text-3xl' : size === 'sm' ? 'text-lg' : 'text-2xl';
  return (
    <div className={`panel px-3 py-2 flex flex-col justify-between min-w-0 ${className}`}>
      <div className="panel-title truncate">{label}</div>
      <div className="flex items-baseline gap-1 mt-1 min-w-0">
        <span className={`num font-mono ${valueCls} font-semibold leading-none truncate`} style={{ color }}>
          {value ?? '—'}
        </span>
        {unit && <span className="text-[11px] text-ink-faint">{unit}</span>}
      </div>
      {spark && spark.length > 1 && <Sparkline data={spark} color={color} />}
      {progress !== undefined && progress !== null && (
        <div className="mt-2 h-1 w-full rounded-full bg-edge overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.max(0, progress * 100))}%`, background: progressColor }} />
        </div>
      )}
      {sub && <div className="mt-1 text-[11px] text-ink-dim num truncate">{sub}</div>}
    </div>
  );
}

export function Sparkline({ data, color, height = 22 }: { data: number[]; color: string; height?: number }) {
  const w = 120;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${height - ((v - min) / span) * (height - 2) - 1}`).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="mt-1 w-full" style={{ height }} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
