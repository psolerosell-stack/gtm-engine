import { useState } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Sparkles, RefreshCw, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import { KpiCard } from "@/components/KpiCard";
import { TierBadge } from "@/components/TierBadge";
import { useOverviewKPIs, useFunnelStats, usePartnerPerformance, useARRTrends, useBriefingToday, useGenerateBriefing } from "@/hooks/useAnalytics";
import { BriefingContent } from "@/api/client";

const fmt = (n: number) =>
  n >= 1_000_000
    ? `€${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000
    ? `€${(n / 1_000).toFixed(0)}k`
    : `€${n.toFixed(0)}`;

function BriefingPanel() {
  const { data: briefing, isLoading } = useBriefingToday();
  const generate = useGenerateBriefing();
  const [generated, setGenerated] = useState(false);

  const handleGenerate = async () => {
    await generate.mutateAsync();
    setGenerated(true);
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border p-6 animate-pulse">
        <div className="h-4 bg-slate-200 rounded w-1/3 mb-4" />
        <div className="h-3 bg-slate-200 rounded w-full mb-2" />
        <div className="h-3 bg-slate-200 rounded w-5/6" />
      </div>
    );
  }

  const parsed: BriefingContent | null = briefing
    ? (() => {
        try {
          return JSON.parse(briefing.content);
        } catch {
          return null;
        }
      })()
    : null;

  const funnelStatus = parsed?.funnel_health?.status ?? "unknown";
  const FunnelIcon =
    funnelStatus === "healthy"
      ? CheckCircle
      : funnelStatus === "at_risk"
      ? AlertTriangle
      : funnelStatus === "critical"
      ? XCircle
      : AlertTriangle;
  const funnelColor =
    funnelStatus === "healthy"
      ? "text-emerald-500"
      : funnelStatus === "at_risk"
      ? "text-amber-500"
      : "text-red-500";

  return (
    <div className="bg-white rounded-lg border p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-violet-500" />
          <h2 className="font-semibold text-slate-800">Daily AI Briefing</h2>
          {briefing && (
            <span className="text-xs text-slate-400 ml-1">
              {new Date(briefing.generated_at).toLocaleDateString()}
            </span>
          )}
        </div>
        <button
          onClick={handleGenerate}
          disabled={generate.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-60 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${generate.isPending ? "animate-spin" : ""}`} />
          {briefing && !generated ? "Regenerate" : "Generate"}
        </button>
      </div>

      {!briefing && !generate.isPending && (
        <p className="text-slate-500 text-sm">
          No briefing generated yet for today. Click Generate to create one.
        </p>
      )}

      {generate.isPending && (
        <div className="flex items-center gap-2 text-violet-600 text-sm">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Generating briefing with AI…
        </div>
      )}

      {parsed && (
        <div className="space-y-4">
          {parsed.headline && (
            <p className="text-slate-700 font-medium">{parsed.headline}</p>
          )}
          {parsed.narrative && (
            <p className="text-slate-600 text-sm leading-relaxed">{parsed.narrative}</p>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {parsed.urgent && parsed.urgent.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-red-600 uppercase tracking-wide mb-1.5">
                  Urgent Actions
                </h3>
                <ul className="space-y-1">
                  {parsed.urgent.map((item, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-sm text-slate-700">
                      <span className="text-red-400 mt-0.5">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {parsed.opportunities && parsed.opportunities.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-emerald-600 uppercase tracking-wide mb-1.5">
                  Opportunities
                </h3>
                <ul className="space-y-1">
                  {parsed.opportunities.map((item, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-sm text-slate-700">
                      <span className="text-emerald-400 mt-0.5">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {parsed.funnel_health && (
            <div className="flex items-center gap-2 mt-2">
              <FunnelIcon className={`w-4 h-4 ${funnelColor}`} />
              <span className="text-sm text-slate-600">
                <span className={`font-medium ${funnelColor}`}>
                  Funnel {funnelStatus}
                </span>
                {parsed.funnel_health.note ? ` — ${parsed.funnel_health.note}` : ""}
              </span>
            </div>
          )}

          {parsed.insights && parsed.insights.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                Key Insights
              </h3>
              <ul className="space-y-1">
                {parsed.insights.map((item, i) => (
                  <li key={i} className="text-sm text-slate-600">
                    — {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Analytics() {
  const { data: kpis, isLoading: kpisLoading } = useOverviewKPIs();
  const { data: funnel = [] } = useFunnelStats();
  const { data: partners = [] } = usePartnerPerformance(8);
  const { data: trends = [] } = useARRTrends(12);

  // Filter funnel to active stages only for chart
  const activeFunnel = funnel.filter(
    (s) => !["closed_won", "closed_lost"].includes(s.stage)
  );

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
        <p className="text-slate-500 text-sm mt-0.5">Revenue intelligence & GTM overview</p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total ARR"
          value={kpisLoading ? "—" : fmt(kpis?.total_arr ?? 0)}
          accent="green"
        />
        <KpiCard
          label="ARR Last 30d"
          value={kpisLoading ? "—" : fmt(kpis?.arr_last_30d ?? 0)}
          accent="blue"
        />
        <KpiCard
          label="Open Pipeline"
          value={kpisLoading ? "—" : fmt(kpis?.open_pipeline_arr ?? 0)}
          sub={`${kpis?.open_deals ?? 0} deals`}
          accent="blue"
        />
        <KpiCard
          label="Active Partners"
          value={kpisLoading ? "—" : String(kpis?.active_partners ?? 0)}
          sub={`Avg ICP: ${kpis?.avg_icp_score ?? 0}`}
          accent="amber"
        />
      </div>

      {/* ARR trend + Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border p-5">
          <h2 className="font-semibold text-slate-800 mb-4">ARR Trend (12 months)</h2>
          {trends.length === 0 ? (
            <p className="text-slate-400 text-sm">No revenue data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={trends} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="arrGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} width={56} />
                <Tooltip formatter={(v: number) => [`€${v.toLocaleString()}`, "ARR"]} />
                <Area
                  type="monotone"
                  dataKey="arr"
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="url(#arrGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-lg border p-5">
          <h2 className="font-semibold text-slate-800 mb-4">Pipeline Funnel</h2>
          {activeFunnel.length === 0 ? (
            <p className="text-slate-400 text-sm">No open opportunities.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={activeFunnel} layout="vertical" margin={{ left: 8, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="stage" type="category" tick={{ fontSize: 11 }} width={90} />
                <Tooltip formatter={(v: number) => [v, "Deals"]} />
                <Bar dataKey="count" fill="#7c3aed" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Partner performance table */}
      <div className="bg-white rounded-lg border">
        <div className="px-5 py-4 border-b">
          <h2 className="font-semibold text-slate-800">Partner Performance</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wide border-b">
                <th className="px-5 py-3">Partner</th>
                <th className="px-5 py-3">Tier</th>
                <th className="px-5 py-3">ICP</th>
                <th className="px-5 py-3 text-right">Total ARR</th>
                <th className="px-5 py-3 text-right">Deals</th>
                <th className="px-5 py-3 text-right">Active</th>
              </tr>
            </thead>
            <tbody>
              {partners.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                    No partner data yet.
                  </td>
                </tr>
              )}
              {partners.map((p) => (
                <tr key={p.partner_id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="px-5 py-3 font-medium text-slate-800">{p.partner_name}</td>
                  <td className="px-5 py-3">
                    <TierBadge tier={p.tier} />
                  </td>
                  <td className="px-5 py-3 text-slate-600">{p.icp_score.toFixed(0)}</td>
                  <td className="px-5 py-3 text-right font-medium text-emerald-700">
                    {fmt(p.total_arr)}
                  </td>
                  <td className="px-5 py-3 text-right text-slate-600">{p.opportunity_count}</td>
                  <td className="px-5 py-3 text-right text-slate-600">{p.active_opportunities}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Daily Briefing */}
      <BriefingPanel />
    </div>
  );
}
