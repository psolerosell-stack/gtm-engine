import React, { useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { usePartners } from "@/hooks/usePartners";
import { TierBadge } from "@/components/TierBadge";
import { ScoreBar } from "@/components/ScoreBar";
import { Partner } from "@/api/client";

const col = createColumnHelper<Partner>();

const columns = [
  col.accessor((row) => row.account?.name ?? "Unknown", {
    id: "account_name",
    header: "Partner",
    cell: (info) => <span className="font-medium text-gray-900">{info.getValue()}</span>,
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
  col.accessor("status", {
    header: "Status",
    cell: (info) => (
      <span className="capitalize text-sm text-gray-600">{info.getValue()}</span>
    ),
  }),
  col.accessor("geography", {
    header: "Geography",
    cell: (info) => info.getValue() ?? "—",
  }),
  col.accessor("vertical", {
    header: "Vertical",
    cell: (info) => info.getValue() ?? "—",
  }),
  col.accessor("arr_potential", {
    header: "ARR Potential",
    cell: (info) =>
      info.getValue() != null ? `€${(info.getValue()! / 1000).toFixed(0)}k` : "—",
  }),
];

export function PartnerHealth() {
  const [sorting, setSorting] = useState<SortingState>([{ id: "icp_score", desc: true }]);
  const [tierFilter, setTierFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const { data, isLoading } = usePartners({
    page_size: 100,
    tier: tierFilter || undefined,
    type: typeFilter || undefined,
  });

  const partners = data?.items ?? [];
  const platinum = partners.filter((p) => p.tier === "Platinum").length;
  const gold = partners.filter((p) => p.tier === "Gold").length;
  const active = partners.filter((p) => p.status === "active").length;
  const avgScore =
    partners.length > 0
      ? (partners.reduce((s, p) => s + p.icp_score, 0) / partners.length).toFixed(1)
      : "—";

  const table = useReactTable({
    data: partners,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Partner Health</h1>
        <p className="text-sm text-gray-500">ICP scores, tiers, and engagement status</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Partners", value: data?.total ?? 0 },
          { label: "Active", value: active },
          { label: "Platinum / Gold", value: `${platinum} / ${gold}` },
          { label: "Avg ICP Score", value: avgScore },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-2 py-1 bg-white"
        >
          <option value="">All tiers</option>
          {["Platinum", "Gold", "Silver", "Bronze"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-2 py-1 bg-white"
        >
          <option value="">All types</option>
          {["OEM", "VAR+", "VAR", "Referral", "Alliance"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {/* Table */}
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
    </div>
  );
}
