import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { usePartners } from "@/hooks/usePartners";
import { useEnrichAccount } from "@/hooks/useAccounts";
import { TierBadge } from "@/components/TierBadge";
import { ScoreBar } from "@/components/ScoreBar";
import { KpiCard } from "@/components/KpiCard";
import { LogActivityModal } from "@/components/LogActivityModal";
import { Partner } from "@/api/client";

export function PartnerSourcing() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [logTarget, setLogTarget] = useState<Partner | null>(null);
  const [enrichingIds, setEnrichingIds] = useState<Set<string>>(new Set());

  const tierFilter = searchParams.get("tier") ?? "";
  const typeFilter = searchParams.get("type") ?? "";

  function set(key: string, value: string) {
    const p = new URLSearchParams(searchParams);
    if (value) p.set(key, value); else p.delete(key);
    setSearchParams(p);
  }

  const { data, isLoading } = usePartners({
    status: "prospect",
    tier: tierFilter || undefined,
    type: typeFilter || undefined,
    page_size: 100,
  });

  const { mutateAsync: enrich } = useEnrichAccount();

  const prospects = data?.items ?? [];
  const highICP = prospects.filter((p) => p.icp_score >= 70).length;
  const pendingEnrichment = prospects.filter((p) => p.fit_summary == null).length;

  async function handleEnrich(partner: Partner) {
    if (!partner.account_id) return;
    setEnrichingIds((prev) => new Set(prev).add(partner.id));
    try {
      await enrich({ id: partner.account_id });
    } finally {
      setEnrichingIds((prev) => {
        const next = new Set(prev);
        next.delete(partner.id);
        return next;
      });
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Partner Sourcing</h1>
        <p className="text-sm text-gray-500">Discovery queue — ICP-scored prospects not yet activated</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <KpiCard label="Prospects" value={data?.total ?? 0} />
        <KpiCard label="High ICP (≥70)" value={highICP} accent="green" />
        <KpiCard label="Pending Enrichment" value={pendingEnrichment} accent="amber" />
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={tierFilter}
          onChange={(e) => set("tier", e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white"
        >
          <option value="">All tiers</option>
          {["Platinum", "Gold", "Silver", "Bronze"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => set("type", e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white"
        >
          <option value="">All types</option>
          {["OEM", "VAR+", "VAR", "Referral", "Alliance"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
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
                {partner.geography && <span>{partner.geography}</span>}
                {partner.vertical && <span>{partner.vertical}</span>}
                {partner.account?.erp_ecosystem && (
                  <span>{partner.account.erp_ecosystem.replace(/_/g, " ")}</span>
                )}
              </div>
              {partner.fit_summary ? (
                <p className="text-sm text-gray-600 line-clamp-2">{partner.fit_summary}</p>
              ) : (
                <p className="text-xs text-amber-600 italic">Enrichment pending — run AI enrichment to generate fit summary</p>
              )}
            </div>
            <div className="w-32 shrink-0">
              <div className="text-xs text-gray-400 mb-1">ICP Score</div>
              <ScoreBar score={partner.icp_score} />
            </div>
            <div className="shrink-0 flex flex-col gap-2">
              <button
                onClick={() => setLogTarget(partner)}
                className="text-xs text-gray-600 border border-gray-200 px-3 py-1.5 rounded-md hover:bg-gray-50 transition-colors"
              >
                Log Contact
              </button>
              {!partner.fit_summary && (
                <button
                  onClick={() => handleEnrich(partner)}
                  disabled={enrichingIds.has(partner.id)}
                  className="text-xs bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white px-3 py-1.5 rounded-md transition-colors"
                >
                  {enrichingIds.has(partner.id) ? "Enriching…" : "Enrich AI"}
                </button>
              )}
            </div>
          </div>
        ))}
        {!isLoading && prospects.length === 0 && (
          <div className="text-sm text-gray-400 text-center py-12">No prospects in queue</div>
        )}
      </div>

      {logTarget && (
        <LogActivityModal
          entityType="partner"
          entityId={logTarget.id}
          entityName={logTarget.account?.name}
          onClose={() => setLogTarget(null)}
        />
      )}
    </div>
  );
}
