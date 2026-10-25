import type { SportCategory } from '@/api/types';
import { SPORT_COLOR, SPORT_LABEL } from '@/lib/colors';

export default function SportBadge({ category, type }: { category: SportCategory; type?: string | null }) {
  const color = SPORT_COLOR[category] ?? SPORT_COLOR.other;
  return (
    <span
      className="inline-flex items-center px-1.5 h-5 rounded-[2px] text-[10px] font-medium uppercase tracking-wide"
      style={{ background: `${color}22`, color, border: `1px solid ${color}55` }}
      title={type ?? category}
    >
      {SPORT_LABEL[category] ?? category}
    </span>
  );
}
