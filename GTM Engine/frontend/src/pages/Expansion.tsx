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
import { useAccounts } from "@/hooks/useAccounts";
import { useOpportunities } from "@/hooks/useOpportunities";
import { KpiCard } from "@/components/KpiCard";
import { LogActivityModal } from "@/components/LogActivityModal";
import { Account } from "@/api/client";
import { formatCurrency } from "@/utils/format";

interface ExpansionRow extends Account {
  wonCount: number;
  wonARR: number;
  openARR: number;
  hasSignals: boolean;
}

const col = createColumnHelper<ExpansionRow>();

export function Expansion() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sorting, setSorting] = useState<SortingState>([{ id: "wonARR", desc: true }]);
  const [logTarget, setLogTarget] = useState<Account | null>(null);

  const industryFilter = searchParams.get("industry") ?? "";
  const signalsOnly = searchParams.get("signals") === "1";

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

  const { data: accountsData, isLoading } = useAccounts({ page_size: 200 });
  const { data: oppsData } = useOpportunities({ page_size: 500 });

  const accounts = accountsData?.items ?? [];
  const allOpps = oppsData?.items ?? [];

  // Only accounts with at least one closed-won deal (existing clients with expansion potential)
  const rows: ExpansionRow[] = accounts
    .map((acc) => {
      const accOpps = allOpps.filter((o) => o.account_id === acc.id);
      const wonOpps = accOpps.filter((o) => o.stage === "closed_won");
      const openOpps = accOpps.filter((o) => !["closed_won", "closed_lost"].includes(o.stage));
      const wonARR = wonOpps.reduce((s, o) => s + (o.arr_value ?? 0), 0);
      const openARR = openOpps.reduce((s, o) => s + (o.arr_value ?? 0), 0);
      const hasSignals = Boolean(acc.fit_summary) && wonOpps.length > 0;
      return {
        ...acc,
        wonCount: wonOpps.length,
        wonARR,
        openARR,
        hasSignals,
      };
    })
    .filter((r) => r.wonCount > 0);

  const industries = [...new Set(rows.map((r) => r.industry).filter(Boolean) as string[])].sort();

  const filtered = rows.filter((r) => {
    if (industryFilter && r.industry !== industryFilter) return false;
    if (signalsOnly && !r.hasSignals) return false;
    return true;
  });

  const totalWonARR = rows.reduce((s, r) => s + r.wonARR, 0);
  const totalOpenARR = rows.reduce((s, r) => s + r.openARR, 0);
  const withSignals = rows.filter((r) => r.hasSignals).length;
  const multiProduct = rows.filter((r) => r.wonCount > 1).length;

  const columns = [
    col.accessor("name", {
      header: "Account",
      cell: (info) => <span className="font-medium text-gray-900">{info.getValue()}</span>,
    }),
    col.accessor("industry", {
      header: "Industry",
      cell: (info) => info.getValue() ?? "—",
    }),
    col.accessor((r) => r.erp_ecosystem ?? "—", {
      id: "erp",
      header: "ERP",
      cell: (info) => (
        <span className="text-xs text-gray-500">{info.getValue().replace(/_/g, " ")}</span>
      ),
    }),
    col.accessor("wonCount", {
      header: "Closed Won",
      cell: (info) => (
        <span className="font-medium text-green-700">{info.getValue()}</span>
      ),
    }),
    col.accessor("wonARR", {
      header: "Won ARR",
      cell: (info) => (
        <span className="font-medium text-gray-900">{formatCurrency(info.getValue())}</span>
      ),
    }),
    col.accessor("openARR", {
      header: "Open Pipeline",
      cell: (info) =>
        info.getValue() > 0 ? (
          <span className="text-blue-700 font-medium">{formatCurrency(info.getValue())}</span>
        ) : (
          <span className="text-gray-400">—</span>
        ),
    }),
    col.accessor("hasSignals", {
      header: "Signals",
      cell: (info) =>
        info.getValue() ? (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">Has signals</span>
        ) : (
          <span className="text-xs text-gray-400">—</span>
        ),
    }),
    col.accessor("fit_summary", {
      header: "Fit Note",
      cell: (info) =>
        info.getValue() ? (
          <span className="text-xs text-gray-600 line-clamp-2 max-w-xs">{info.getValue()}</span>
        ) : (
          <span className="text-xs text-gray-400 italic">No note</span>
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
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Account Expansion</h1>
        <p className="text-sm text-gray-500">Existing clients with expansion signals and open upsell pipeline</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="Expansion Accounts" value={rows.length} />
        <KpiCard label="Won ARR Base" value={formatCurrency(totalWonARR)} accent="green" />
        <KpiCard label="Open Upsell ARR" value={formatCurrency(totalOpenARR)} accent="blue" />
        <KpiCard label="With Signals" value={withSignals} sub={`${multiProduct} multi-product`} />
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={industryFilter}
          onChange={(e) => set("industry", e.target.value)}
          className="text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white"
        >
          <option value="">All industries</option>
          {industries.map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={signalsOnly}
            onChange={(e) => toggle("signals", e.target.checked)}
            className="rounded border-gray-300"
          />
          With signals only
        </label>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Loading accounts…</div>
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
                    No expansion accounts found
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
          entityType="account"
          entityId={logTarget.id}
          entityName={logTarget.name}
          onClose={() => setLogTarget(null)}
        />
      )}
    </div>
  );
}
