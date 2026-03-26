import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { useOpportunities, usePipelineSummary } from "@/hooks/useOpportunities";
import { StageBadge } from "@/components/StageBadge";
import { Opportunity } from "@/api/client";
import { formatCurrency } from "@/utils/format";

const STAGE_ORDER = [
  "prospecting",
  "qualification",
  "discovery",
  "demo",
  "proposal",
  "negotiation",
  "closed_won",
  "closed_lost",
];

const STAGE_COLORS: Record<string, string> = {
  prospecting: "#94a3b8",
  qualification: "#60a5fa",
  discovery: "#818cf8",
  demo: "#a78bfa",
  proposal: "#fbbf24",
  negotiation: "#f97316",
  closed_won: "#22c55e",
  closed_lost: "#f87171",
};

const col = createColumnHelper<Opportunity>();

const columns = [
  col.accessor("name", {
    header: "Deal",
    cell: (info) => <span className="font-medium text-gray-900">{info.getValue()}</span>,
  }),
  col.accessor("account", {
    header: "Account",
    cell: (info) => info.getValue()?.name ?? "—",
  }),
  col.accessor("stage", {
    header: "Stage",
    cell: (info) => <StageBadge stage={info.getValue()} />,
  }),
  col.accessor("arr_value", {
    header: "ARR",
    cell: (info) => (info.getValue() != null ? formatCurrency(info.getValue()!) : "—"),
  }),
  col.accessor("close_date", {
    header: "Close Date",
    cell: (info) => info.getValue() ?? "—",
  }),
  col.accessor("owner", {
    header: "Owner",
    cell: (info) => info.getValue() ?? "—",
  }),
];

export function PipelineReview() {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [stageFilter, setStageFilter] = useState<string>("");
  const { data: opps, isLoading } = useOpportunities({ stage: stageFilter || undefined, page_size: 50 });
  const { data: summary } = usePipelineSummary();

  const chartData = STAGE_ORDER.map((s) => ({
    stage: s.replace(/_/g, " "),
    count: summary?.[s]?.count ?? 0,
    arr: summary?.[s]?.total_arr ?? 0,
    key: s,
  })).filter((d) => d.count > 0);

  const totalARR = Object.values(summary ?? {}).reduce((a, b) => a + b.total_arr, 0);
  const openDeals = Object.entries(summary ?? {})
    .filter(([s]) => !["closed_won", "closed_lost"].includes(s))
    .reduce((a, [, v]) => a + v.count, 0);

  const table = useReactTable({
    data: opps?.items ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Pipeline Review</h1>
        <p className="text-sm text-gray-500">All active opportunities across stages</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Open Deals", value: openDeals },
          { label: "Total Pipeline ARR", value: formatCurrency(totalARR) },
          { label: "Won ARR", value: formatCurrency(summary?.closed_won?.total_arr ?? 0) },
          { label: "Avg Deal Size", value: formatCurrency(openDeals > 0 ? totalARR / openDeals : 0) },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{value}</div>
          </div>
        ))}
      </div>

      {/* Pipeline chart */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-sm font-medium text-gray-700 mb-3">Deal distribution by stage</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="stage" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(val: number, name: string) =>
                  name === "arr" ? [formatCurrency(val), "ARR"] : [val, "Deals"]
                }
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={entry.key} fill={STAGE_COLORS[entry.key] ?? "#94a3b8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Stage filter */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-600">Filter by stage:</label>
        <select
          value={stageFilter}
          onChange={(e) => setStageFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-2 py-1 bg-white"
        >
          <option value="">All stages</option>
          {STAGE_ORDER.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Loading opportunities…</div>
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
                    No opportunities found
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
