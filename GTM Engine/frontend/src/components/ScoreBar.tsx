import React from "react";
import { clsx } from "clsx";

function scoreColor(score: number): string {
  if (score >= 85) return "bg-purple-500";
  if (score >= 70) return "bg-yellow-400";
  if (score >= 50) return "bg-blue-400";
  return "bg-gray-300";
}

export function ScoreBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={clsx("h-full rounded-full transition-all", scoreColor(score))}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-700 w-8 text-right">{score.toFixed(0)}</span>
    </div>
  );
}
