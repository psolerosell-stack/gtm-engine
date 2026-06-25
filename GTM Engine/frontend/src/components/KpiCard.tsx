interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "default" | "green" | "amber" | "red" | "blue";
  badge?: string;
  progress?: number; // 0–100
}

const BORDER: Record<string, string> = {
  default: "border-t-white/20",
  green:   "border-t-accent-green",
  blue:    "border-t-accent-blue",
  amber:   "border-t-accent-amber",
  red:     "border-t-accent-red",
};

const BADGE_STYLE: Record<string, string> = {
  green: "bg-accent-green/15 text-accent-green",
  amber: "bg-accent-amber/15 text-accent-amber",
  red:   "bg-accent-red/15 text-accent-red",
  blue:  "bg-accent-blue/15 text-accent-blue",
};

const PROGRESS_COLOR: Record<string, string> = {
  green: "bg-accent-green",
  amber: "bg-accent-amber",
  red:   "bg-accent-red",
  blue:  "bg-accent-blue",
  default: "bg-white/30",
};

export function KpiCard({
  label,
  value,
  sub,
  accent = "default",
  badge,
  progress,
}: KpiCardProps) {
  return (
    <div
      className={`bg-navy-800 rounded-xl border-t-[3px] ${BORDER[accent]} p-4 flex flex-col gap-1`}
    >
      <div className="text-[11px] font-semibold text-muted uppercase tracking-widest">
        {label}
      </div>

      <div className="flex items-end justify-between gap-2 mt-1">
        <div className="text-[28px] font-bold text-white leading-none">{value}</div>
        {badge && (
          <span
            className={`text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${
              BADGE_STYLE[accent] ?? BADGE_STYLE.blue
            }`}
          >
            {badge}
          </span>
        )}
      </div>

      {sub && (
        <div className="text-xs text-muted mt-0.5">{sub}</div>
      )}

      {progress != null && (
        <div className="mt-2 h-1 rounded-full bg-white/10 overflow-hidden">
          <div
            className={`h-full rounded-full ${PROGRESS_COLOR[accent]}`}
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      )}
    </div>
  );
}
