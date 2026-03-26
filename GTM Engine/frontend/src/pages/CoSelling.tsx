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
import { useOpportunities } from "@/hooks/useOpportunities";
import { StageBadge } from "@/components/StageBadge";
import { KpiCard } from "@/components/KpiCard";
import { LogActivityModal } from "@/components/LogActivityModal";
import { UpdateStageModal } from "@/components/UpdateStageModal";
import { Opportunity } from "@/api/client";
import { formatCurrency, formatDate } from "@/utils/format";

const ACTIVE_STAGES = ["prospecting", "qualification", "discovery", "demo", "proposal", "negotiation"];

const col = createColumnHelper<Opportunity>();

export function CoSelling() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sorting, setSorting] = useState<SortingState>([{ id: "arr_value", desc: true }]);
  const [logTarget, setLogTarget] = useState<Opportunity | null>(null);
  const [stageTarget, setStageTarget] = useState<Opportunity | null>(null);

  const stageFilter = searchParams.get("stage") ?? "";

  function set(key: string, value: string) {
    const p = new URLSearchParams(searchParams);
    if (value) p.set(key, value); else p.delete(key);
    setSearchParams(p);
  }

  // Only deals with a partner assigned
  const { data, isLoading } = useOpportunities({
    stage: stageFilter || undefined,
    page_size: 200,
  });

  const allOpps = data?.items ?? [];
  const coSellOpps = allOpps.filter((o) => o.partner_id);
  const activeOpps = coSellOpps.filter((o) => ACTIVE_STAGES.includes(o.stage));

  const today = new Date();
  const atRisk = activeOpps.filter(
    (o) => o.close_date && new Date(o.close_date) < today
  ).length;

  const totalARR = activeOpps.reduce((s, o) => s + (o.arr_value ?? 0), 0);
  const avgDeal =
    activeOpps.length > 0 ? totalARR / activeOpps.length : 0;

  const displayOpps = stageFilter
    ? coSellOpps.filter((o) => o.stage === stageFilter)
    : coSellOpps;

  const columns = [
    col.accessor("name", {
      header: "Deal",
      cell: (info) => <span className="font-medium text-gray-900">{info.getValue()}</span>,
    }),
    col.accessor((r) => r.account?.name ?? "—", {
      id: "account",
      header: "Account",
    }),
    col.accessor((r) => r.partner?.type ?? "—", {
      id: "partner_type",
      header: "Partner Type",
      cell: (info) => <span className="text-xs text-gray-600">{info.getValue()}</span>,
    }),
    col.accessor("stage", {
      header: "Stage",
      cell: (info) => <StageBadge stage={info.getValue()} />,
    }),
    col.accessor("arr_value", {
      header: "ARR",
      cell: (info) =>
        info.getValue() != null ? (
          <span className="font-medium">{formatCurrency(info.getValue()!)}</span>
        ) : (
          "—"
        ),
    }),
    col.accessor("close_date", {
      header: "Close Date",
      cell: (info) => {
        const val = info.getValue();
        if (!val) return "—";
        const isPast = new Date(val) < today && ACTIVE_STAGES.includes(info.row.original.stage);
        return (
          <span className={isPast ? "text-red-600 font-medium" : "text-gray-700"}>
            {formatDate(val)}
          </span>
        );
      },
    }),
    col.accessor("owner", {
      header: "Owner",
      cell: (info) => info.getValue() ?? "—",
    }),
    col.display({
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex gap-2 justify-end">
          <button
            onClick={() => setStageTarget(row.original)}
            className="text-xs text-gray-600 border border-gray-200 px-2 py-1 rounded hover:bg-gray-50 transition-colors"
          >
            Stage
          </button>
          <button
            onClick={() => setLogTarget(row.original)}
            className="text-xs text-gray-600 border border-gray-200 px-2 py-1 rounded hover:bg-gray-50 transition-colors"
          >
            Log
          </button>
        </div>
      ),
    }),
  ];

  const table = useReactTable({
    data: displayOpps,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Co-selling</h1>
        <p className="text-sm text-gray-500">Shared pipeline — deals with an assigned partner</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="Co-sell Deals" value={activeOpps.length} />
        <KpiCard label="Pipeline ARR" value={formatCurrency(totalARR)} accent="blue" />
        <KpiCard label="Avg Deal Size" value={formatCurrency(avgDeal)} />
        <KpiCard label="At-Risk (Past Close)" value={atRisk} accent={atRisk > 0 ? "red" : "default"} />
      </div>

      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-600">Filter by stage:</label>
        <select
          value={stageFilter}
          onChange={(e) => set("stage", e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white"
        >
          <option value="">All stages</option>
          {[...ACTIVE_STAGES, "closed_won", "closed_lost"].map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Loading pipeline…</div>
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
                    No co-sell deals found
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
          entityType="opportunity"
          entityId={logTarget.id}
          entityName={logTarget.name}
          onClose={() => setLogTarget(null)}
        />
      )}
      {stageTarget && (
        <UpdateStageModal
          opportunity={stageTarget}
          onClose={() => setStageTarget(null)}
        />
      )}
    </div>
  );
}
