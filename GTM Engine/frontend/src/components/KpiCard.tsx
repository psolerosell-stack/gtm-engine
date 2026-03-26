import { clsx } from "clsx";

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "default" | "green" | "amber" | "red" | "blue";
}

const ACCENT: Record<string, string> = {
  default: "text-gray-900",
  green: "text-green-600",
  amber: "text-amber-600",
  red: "text-red-600",
  blue: "text-blue-600",
};

export function KpiCard({ label, value, sub, accent = "default" }: KpiCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className={clsx("text-2xl font-bold mt-1", ACCENT[accent])}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}
