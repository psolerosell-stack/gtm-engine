import React from "react";
import { usePartners } from "@/hooks/usePartners";
import { TierBadge } from "@/components/TierBadge";
import { ScoreBar } from "@/components/ScoreBar";

export function PartnerSourcing() {
  const { data, isLoading } = usePartners({ status: "prospect", page_size: 50 });
  const prospects = data?.items ?? [];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Partner Sourcing</h1>
        <p className="text-sm text-gray-500">Discovery queue — prospects not yet contacted</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Prospects", value: data?.total ?? 0 },
          {
            label: "High ICP (≥70)",
            value: prospects.filter((p) => p.icp_score >= 70).length,
          },
          {
            label: "Pending Enrichment",
            value: prospects.filter((p) => p.fit_summary == null).length,
          },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3">
        {isLoading && (
          <div className="text-sm text-gray-400 text-center py-8">Loading prospects…</div>
        )}
        {prospects.map((partner) => (
          <div
            key={partner.id}
            className="bg-white rounded-lg border border-gray-200 p-4 flex items-start gap-4"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold text-gray-900">
                  {partner.account?.name ?? "Unknown Account"}
                </span>
                <TierBadge tier={partner.tier} />
                <span className="text-xs text-gray-400">{partner.type}</span>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500 mb-2">
                {partner.geography && <span>📍 {partner.geography}</span>}
                {partner.vertical && <span>🏭 {partner.vertical}</span>}
                {partner.account?.erp_ecosystem && (
                  <span>🔧 {partner.account.erp_ecosystem.replace(/_/g, " ")}</span>
                )}
              </div>
              {partner.fit_summary ? (
                <p className="text-sm text-gray-600 line-clamp-2">{partner.fit_summary}</p>
              ) : (
                <p className="text-xs text-amber-600 italic">Enrichment pending</p>
              )}
            </div>
            <div className="w-32 shrink-0">
              <div className="text-xs text-gray-400 mb-1">ICP Score</div>
              <ScoreBar score={partner.icp_score} />
            </div>
            <div className="shrink-0">
              <button className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-md transition-colors">
                Contact
              </button>
            </div>
          </div>
        ))}
        {!isLoading && prospects.length === 0 && (
          <div className="text-sm text-gray-400 text-center py-12">No prospects in queue</div>
        )}
      </div>
    </div>
  );
}
