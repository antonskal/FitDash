import type { ReactNode } from 'react';
import { Info } from 'lucide-react';

interface PanelProps {
  title: string;
  subtitle?: string;
  info?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  loading?: boolean;
  empty?: boolean;
  emptyText?: string;
}

export default function Panel({ title, subtitle, info, actions, children, className = '', bodyClassName = '', loading, empty, emptyText = 'No data in this window' }: PanelProps) {
  return (
    <section className={`panel flex flex-col min-w-0 ${className}`}>
      <header className="flex items-center justify-between gap-2 px-3 h-8 border-b border-edge/80">
        <div className="flex items-center gap-1.5 min-w-0">
          <h3 className="panel-title truncate">{title}</h3>
          {subtitle && <span className="text-[10px] text-ink-faint truncate">{subtitle}</span>}
          {info && (
            <span title={info} className="text-ink-faint hover:text-ink-dim cursor-help">
              <Info size={11} />
            </span>
          )}
          {loading && <span className="ml-1 h-1.5 w-1.5 rounded-full bg-blue pulse" />}
        </div>
        {actions && <div className="flex items-center gap-1 shrink-0">{actions}</div>}
      </header>
      <div className={`relative flex-1 min-h-0 p-2 ${bodyClassName}`}>
        {empty && !loading ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-ink-faint">{emptyText}</div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}
