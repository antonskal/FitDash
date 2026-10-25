import type { ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useDashboard } from '@/store/dashboard';

interface RowProps {
  id: string;
  title: string;
  hint?: string;
  children: ReactNode;
  actions?: ReactNode;
}

/** Grafana-style collapsible dashboard row. */
export default function Row({ id, title, hint, children, actions }: RowProps) {
  const collapsed = useDashboard((s) => !!s.collapsedRows[id]);
  const toggle = useDashboard((s) => s.toggleRow);
  return (
    <div className="mb-2">
      <div className="flex items-center gap-2 h-7 px-1 group">
        <button onClick={() => toggle(id)} className="flex items-center gap-1.5 text-ink-dim hover:text-ink text-xs font-semibold">
          {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
          <span>{title}</span>
        </button>
        {hint && <span className="text-[10px] text-ink-faint hidden md:inline">{hint}</span>}
        <div className="flex-1 h-px bg-edge" />
        {actions && <div className="flex items-center gap-1">{actions}</div>}
      </div>
      {!collapsed && <div className="mt-1">{children}</div>}
    </div>
  );
}
