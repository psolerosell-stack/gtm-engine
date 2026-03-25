import React from "react";

interface Props {
  title: string;
  description: string;
}

export function Placeholder({ title, description }: Props) {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-gray-900">{title}</h1>
      <p className="text-sm text-gray-500 mt-1">{description}</p>
      <div className="mt-8 bg-white rounded-lg border border-dashed border-gray-300 p-12 text-center">
        <p className="text-gray-400 text-sm">Coming in Layer 5 — full view implementation</p>
      </div>
    </div>
  );
}
