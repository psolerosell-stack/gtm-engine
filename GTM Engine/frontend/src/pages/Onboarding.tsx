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
import { useActivities } from "@/hooks/useActivities";
import { TierBadge } from "@/components/TierBadge";
import { KpiCard } from "@/components/KpiCard";
import { LogActivityModal } from "@/components/LogActivityModal";
import { Partner } from "@/api/client";

interface OnboardingRow extends Partner {
  daysSinceStart: number;
  lastActivityDate: string | null;
  daysSinceContact: number | null;
}

const col = createColumnHelper<OnboardingRow>();

function StatusPill({ days }: { days: number }) {
  if (days <= 14) return <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">On track</span>;
  if (days <= 30) return <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">Slow</span>;
  return <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">Stalled</span>;
}

export function Onboarding() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sorting, setSorting] = useState<SortingState>([{ id: "daysSinceStart", desc: true }]);
  const [logTarget, setLogTarget] = useState<Partner | null>(null);

  const typeFilter = searchParams.get("type") ?? "";

  function set(key: string, value: string) {
    const p = new URLSearchParams(searchParams);
    if (value) p.set(key, value); else p.delete(key);
    setSearchParams(p);
  }

  const { data: partnersData, isLoading } = usePartners({
    status: "pending",
    type: typeFilter || undefined,
    page_size: 100,
  });

  const { data: activities } = useActivities({ entity_type: "partner" });

  const partners = partnersData?.items ?? [];
  const activityList = activities ?? [];

  const now = new Date();

  const rows: OnboardingRow[] = partners.map((p) => {
    const daysSinceStart = Math.floor(
      (now.getTime() - new Date(p.created_at).getTime()) / 86_400_000
    );

    const partnerActivities = activityList
      .filter((a) => a.entity_id === p.id)
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    const lastActivityDate = partnerActivities[0]?.date ?? null;
    const daysSinceContact = lastActivityDate
      ? Math.floor((now.getTime() - new Date(lastActivityDate).getTime()) / 86_400_000)
      : null;

    return { ...p, daysSinceStart, lastActivityDate, daysSinceContact };
  });

  const stalled = rows.filter((r) => r.daysSinceStart > 30).length;
  const slow = rows.filter((r) => r.daysSinceStart > 14 && r.daysSinceStart <= 30).length;
  const avgDays = rows.length > 0
    ? Math.round(rows.reduce((s, r) => s + r.daysSinceStart, 0) / rows.length)
    : 0;
  const noContact = rows.filter((r) => r.daysSinceContact === null || r.daysSinceContact > 7).length;

  const columns = [
    col.accessor((r) => r.account?.name ?? "—", {
      id: "account_name",
      header: "Partner",
      cell: (info) => <span className="font-medium text-gray-900">{info.getValue()}</span>,
    }),
    col.accessor("type", { header: "Type" }),
    col.accessor("tier", {
      header: "Tier",
      cell: (info) => <TierBadge tier={info.getValue()} />,
    }),
    col.accessor("daysSinceStart", {
      header: "Days in Onboarding",
      cell: (info) => (
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900">{info.getValue()}d</span>
          <StatusPill days={info.getValue()} />
        </div>
      ),
    }),
    col.accessor("daysSinceContact", {
      header: "Last Contact",
      cell: (info) => {
        const val = info.getValue();
        if (val === null) return <span className="text-red-500 text-xs font-medium">Never</span>;
        return (
          <span className={val > 7 ? "text-amber-600 font-medium text-sm" : "text-gray-700 text-sm"}>
            {val === 0 ? "Today" : `${val}d ago`}
          </span>
        );
      },
    }),
    col.accessor("geography", {
      header: "Geography",
      cell: (info) => info.getValue() ?? "—",
    }),
    col.accessor("icp_score", {
      header: "ICP",
      cell: (info) => (
        <span className="font-medium text-gray-700">{info.getValue().toFixed(0)}</span>
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
        <h1 className="text-xl font-bold text-gray-900">Onboarding</h1>
        <p className="text-sm text-gray-500">Partners in pending status — track progress and unblock activation</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="In Onboarding" value={partners.length} />
        <KpiCard label="Stalled (>30d)" value={stalled} accent={stalled > 0 ? "red" : "default"} />
        <KpiCard label="Slow (15–30d)" value={slow} accent={slow > 0 ? "amber" : "default"} />
        <KpiCard label="Needs Contact" value={noContact} accent={noContact > 0 ? "amber" : "default"} sub={`avg ${avgDays}d`} />
      </div>

      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-600">Filter by type:</label>
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
          <div className="p-8 text-center text-sm text-gray-500">Loading onboarding partners…</div>
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
                    No partners in onboarding
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
