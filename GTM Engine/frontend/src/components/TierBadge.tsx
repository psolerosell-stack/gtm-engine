import { clsx } from "clsx";

const TIER_STYLES: Record<string, string> = {
  Platinum: "bg-purple-100 text-purple-800 border border-purple-200",
  Gold: "bg-yellow-100 text-yellow-800 border border-yellow-200",
  Silver: "bg-gray-100 text-gray-700 border border-gray-200",
  Bronze: "bg-orange-100 text-orange-700 border border-orange-200",
};

export function TierBadge({ tier }: { tier: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
        TIER_STYLES[tier] ?? "bg-gray-100 text-gray-600"
      )}
    >
      {tier}
    </span>
  );
}
