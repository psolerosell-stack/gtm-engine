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
import { TierBadge } from "@/components/TierBadge";
import { ScoreBar } from "@/components/ScoreBar";
import { KpiCard } from "@/components/KpiCard";
import { LogActivityModal } from "@/components/LogActivityModal";
import { Partner } from "@/api/client";

const col = createColumnHelper<Partner>();

export function Outbound() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sorting, setSorting] = useState<SortingState>([{ id: "icp_score", desc: true }]);
  const [logTarget, setLogTarget] = useState<Partner | null>(null);

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

  const partners = data?.items ?? [];
  const withApproach = partners.filter((p) => p.approach_suggestion).length;
  const highICP = partners.filter((p) => p.icp_score >= 70).length;
  const withoutContact = partners.filter((p) => !p.fit_summary).length;

  const columns = [
    col.accessor((r) => r.account?.name ?? "—", {
      id: "account_name",
      header: "Company",
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
    col.accessor((r) => r.account?.erp_ecosystem ?? "—", {
      id: "erp",
      header: "ERP",
      cell: (info) => (
        <span className="text-xs text-gray-500">{info.getValue().replace(/_/g, " ")}</span>
      ),
    }),
    col.accessor("geography", {
      header: "Geography",
      cell: (info) => info.getValue() ?? "—",
    }),
    col.accessor("approach_suggestion", {
      id: "approach",
      header: "Approach",
      cell: (info) =>
        info.getValue() ? (
          <span className="text-xs text-gray-600 line-clamp-2 max-w-xs">
            {info.getValue()}
          </span>
        ) : (
          <span className="text-xs text-gray-400 italic">Pending AI</span>
        ),
    }),
    col.display({
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex gap-2 justify-end">
          <button
            onClick={() => setLogTarget(row.original)}
            className="text-xs text-gray-600 border border-gray-200 px-2 py-1 rounded hover:bg-gray-50 transition-colors"
          >
            Log Contact
          </button>
          <button className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700 transition-colors">
            Outreach
          </button>
        </div>
      ),
    }),
  ];

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
        <h1 className="text-xl font-bold text-gray-900">Outbound Partnerships</h1>
        <p className="text-sm text-gray-500">ICP-scored prospects not yet contacted</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="Total Prospects" value={data?.total ?? 0} />
        <KpiCard label="High ICP (≥70)" value={highICP} accent="green" />
        <KpiCard label="With Approach" value={withApproach} accent="blue" />
        <KpiCard label="Pending Enrichment" value={withoutContact} accent="amber" />
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

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Loading prospects…</div>
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
                    No outbound prospects
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
