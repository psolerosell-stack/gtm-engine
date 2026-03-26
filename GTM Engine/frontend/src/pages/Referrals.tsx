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
import { KpiCard } from "@/components/KpiCard";
import { LogActivityModal } from "@/components/LogActivityModal";
import { Partner } from "@/api/client";
import { formatCurrency } from "@/utils/format";

interface ReferralRow extends Partner {
  opportunityCount: number;
  wonARR: number;
  conversionRate: number;
}

const col = createColumnHelper<ReferralRow>();

export function Referrals() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sorting, setSorting] = useState<SortingState>([{ id: "wonARR", desc: true }]);
  const [logTarget, setLogTarget] = useState<Partner | null>(null);

  const tierFilter = searchParams.get("tier") ?? "";

  function set(key: string, value: string) {
    const p = new URLSearchParams(searchParams);
    if (value) p.set(key, value); else p.delete(key);
    setSearchParams(p);
  }

  const { data: partnersData, isLoading: partnersLoading } = usePartners({
    type: "Referral",
    tier: tierFilter || undefined,
    page_size: 100,
  });

  const { data: oppsData } = useOpportunities({ page_size: 200 });

  const referralPartners = partnersData?.items ?? [];
  const allOpps = oppsData?.items ?? [];

  const rows: ReferralRow[] = referralPartners.map((p) => {
    const partnerOpps = allOpps.filter((o) => o.partner_id === p.id);
    const wonOpps = partnerOpps.filter((o) => o.stage === "closed_won");
    const wonARR = wonOpps.reduce((s, o) => s + (o.arr_value ?? 0), 0);
    const conversionRate =
      partnerOpps.length > 0 ? Math.round((wonOpps.length / partnerOpps.length) * 100) : 0;
    return { ...p, opportunityCount: partnerOpps.length, wonARR, conversionRate };
  });

  const totalLeads = rows.reduce((s, r) => s + r.opportunityCount, 0);
  const totalWonARR = rows.reduce((s, r) => s + r.wonARR, 0);
  const avgConversion =
    rows.length > 0
      ? Math.round(rows.reduce((s, r) => s + r.conversionRate, 0) / rows.length)
      : 0;

  const columns = [
    col.accessor((r) => r.account?.name ?? "—", {
      id: "account_name",
      header: "Partner",
      cell: (info) => <span className="font-medium text-gray-900">{info.getValue()}</span>,
    }),
    col.accessor("tier", {
      header: "Tier",
      cell: (info) => <TierBadge tier={info.getValue()} />,
    }),
    col.accessor("icp_score", {
      header: "ICP Score",
      cell: (info) => (
        <span className="font-medium text-gray-700">{info.getValue().toFixed(0)}</span>
      ),
    }),
    col.accessor("geography", {
      header: "Geography",
      cell: (info) => info.getValue() ?? "—",
    }),
    col.accessor("opportunityCount", {
      header: "Leads Submitted",
      cell: (info) => <span className="font-medium">{info.getValue()}</span>,
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
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Referrals</h1>
        <p className="text-sm text-gray-500">Active referral partners — leads, conversion, ARR attributed</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="Referral Partners" value={referralPartners.length} />
        <KpiCard label="Leads Submitted" value={totalLeads} accent="blue" />
        <KpiCard label="Won ARR" value={formatCurrency(totalWonARR)} accent="green" />
        <KpiCard label="Avg Conversion" value={`${avgConversion}%`} />
      </div>

      <div className="flex items-center gap-3">
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
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {partnersLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Loading referral partners…</div>
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
                    No referral partners found
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="hover:bg-gray-50 transition-colors">
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
