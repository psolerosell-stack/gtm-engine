import { clsx } from "clsx";

const STAGE_STYLES: Record<string, string> = {
  prospecting: "bg-gray-100 text-gray-600",
  qualification: "bg-blue-100 text-blue-700",
  discovery: "bg-indigo-100 text-indigo-700",
  demo: "bg-violet-100 text-violet-700",
  proposal: "bg-amber-100 text-amber-700",
  negotiation: "bg-orange-100 text-orange-700",
  closed_won: "bg-green-100 text-green-700",
  closed_lost: "bg-red-100 text-red-700",
};

export function StageBadge({ stage }: { stage: string }) {
  const label = stage.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
        STAGE_STYLES[stage] ?? "bg-gray-100 text-gray-600"
      )}
    >
      {label}
    </span>
  );
}
