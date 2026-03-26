import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { usePartners } from "@/hooks/usePartners";
import { useOpportunities } from "@/hooks/useOpportunities";
import { TierBadge } from "@/components/TierBadge";
import { ScoreBar } from "@/components/ScoreBar";
import { KpiCard } from "@/components/KpiCard";
import { LogActivityModal } from "@/components/LogActivityModal";
import { Partner } from "@/api/client";
import { formatCurrency } from "@/utils/format";

interface EnablementRow extends Partner {
  openDeals: number;
  wonARR: number;
  conversionRate: number;
  needsAttention: boolean;
}

const col = createColumnHelper<EnablementRow>();

const ATTENTION_THRESHOLD = 50;

export function Enablement() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sorting, setSorting] = useState<SortingState>([{ id: "icp_score", desc: false }]);
  const [logTarget, setLogTarget] = useState<Partner | null>(null);

  const tierFilter = searchParams.get("tier") ?? "";
  const attentionOnly = searchParams.get("attention") === "1";

  function set(key: string, value: string) {
    const p = new URLSearchParams(searchParams);
    if (value) p.set(key, value); else p.delete(key);
    setSearchParams(p);
  }

  function toggle(key: string, active: boolean) {
    const p = new URLSearchParams(searchParams);
    if (active) p.set(key, "1"); else p.delete(key);
    setSearchParams(p);
  }

  const { data: partnersData, isLoading } = usePartners({
    status: "active",
    tier: tierFilter || undefined,
    page_size: 200,
  });

  const { data: oppsData } = useOpportunities({ page_size: 500 });

  const partners = partnersData?.items ?? [];
  const allOpps = oppsData?.items ?? [];

  const rows: EnablementRow[] = partners.map((p) => {
    const partnerOpps = allOpps.filter((o) => o.partner_id === p.id);
    const activeOpps = partnerOpps.filter(
      (o) => !["closed_won", "closed_lost"].includes(o.stage)
    );
    const wonOpps = partnerOpps.filter((o) => o.stage === "closed_won");
    const wonARR = wonOpps.reduce((s, o) => s + (o.arr_value ?? 0), 0);
    const conversionRate =
      partnerOpps.length > 0
        ? Math.round((wonOpps.length / partnerOpps.length) * 100)
        : 0;
    const needsAttention = p.icp_score < ATTENTION_THRESHOLD || conversionRate < 20;
    return {
      ...p,
      openDeals: activeOpps.length,
      wonARR,
      conversionRate,
      needsAttention,
    };
  });

  const displayRows = attentionOnly ? rows.filter((r) => r.needsAttention) : rows;

  const lowScore = rows.filter((r) => r.icp_score < ATTENTION_THRESHOLD).length;
  const lowConversion = rows.filter((r) => r.conversionRate < 20 && r.conversionRate > 0).length;
  const noDeals = rows.filter((r) => r.openDeals === 0).length;
  const attentionCount = rows.filter((r) => r.needsAttention).length;

  const columns = [
    col.accessor((r) => r.account?.name ?? "—", {
      id: "account_name",
      header: "Partner",
      cell: (info) => (
        <span className="font-medium text-gray-900">{info.getValue()}</span>
      ),
    }),
    col.accessor("type", { header: "Type" }),
    col.accessor("tier", {
      header: "Tier",
      cell: (info) => <TierBadge tier={info.getValue()} />,
    }),
    col.accessor("icp_score", {
      header: "ICP Score",
      cell: (info) => <ScoreBar score={info.getValue()} />,
    }),
    col.accessor("openDeals", {
      header: "Open Deals",
      cell: (info) => (
        <span className={info.getValue() === 0 ? "text-gray-400" : "font-medium text-gray-900"}>
          {info.getValue() === 0 ? "—" : info.getValue()}
        </span>
      ),
    }),
    col.accessor("wonARR", {
      header: "Won ARR",
      cell: (info) =>
        info.getValue() > 0 ? (
          <span className="text-green-700 font-medium">{formatCurrency(info.getValue())}</span>
        ) : (
          <span className="text-gray-400">—</span>
        ),
    }),
    col.accessor("conversionRate", {
      header: "Conversion",
      cell: (info) => (
        <span
          className={
            info.getValue() >= 30
              ? "text-green-700 font-medium"
              : info.getValue() > 0
              ? "text-amber-600 font-medium"
              : "text-gray-400"
          }
        >
          {info.getValue() > 0 ? `${info.getValue()}%` : "—"}
        </span>
      ),
    }),
    col.accessor("needsAttention", {
      header: "Status",
      cell: (info) =>
        info.getValue() ? (
          <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">Needs attention</span>
        ) : (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Healthy</span>
        ),
    }),
    col.accessor("fit_summary", {
      header: "Fit Summary",
      cell: (info) =>
        info.getValue() ? (
          <span className="text-xs text-gray-600 line-clamp-2 max-w-xs">{info.getValue()}</span>
        ) : (
          <span className="text-xs text-gray-400 italic">No summary</span>
        ),
    }),
    col.display({
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <button
          onClick={() => setLogTarget(row.original)}
          className="text-xs text-gray-600 border border-gray-200 px-2 py-1 rounded hover:bg-gray-50 transition-colors"
        >
          Log Activity
        </button>
      ),
    }),
  ];

  const table = useReactTable({
    data: displayRows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Enablement</h1>
        <p className="text-sm text-gray-500">Active partners — score, conversion health, and pipeline activity</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="Active Partners" value={partners.length} />
        <KpiCard label="Need Attention" value={attentionCount} accent={attentionCount > 0 ? "red" : "default"} />
        <KpiCard label="Low Score (<50)" value={lowScore} accent={lowScore > 0 ? "amber" : "default"} />
        <KpiCard label="No Open Deals" value={noDeals} accent={noDeals > 0 ? "amber" : "default"} sub={`${lowConversion} low conversion`} />
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
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={attentionOnly}
            onChange={(e) => toggle("attention", e.target.checked)}
            className="rounded border-gray-300"
          />
          Needs attention only
        </label>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Loading partners…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide cursor-pointer select-none"
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {{ asc: " ↑", desc: " ↓" }[header.column.getIsSorted() as string] ?? ""}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-gray-100">
              {table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-400">
                    No partners found
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className={`hover:bg-gray-50 transition-colors ${row.original.needsAttention ? "bg-red-50/40" : ""}`}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-3 text-gray-700">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
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
