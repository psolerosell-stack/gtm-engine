import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Plus, Trash2 } from "lucide-react";
import { KpiCard } from "@/components/KpiCard";
import { useRevenue, useRevenueSummary, useCreateRevenue, useDeleteRevenue } from "@/hooks/useRevenue";
import { RevenueCreate } from "@/api/client";

const fmt = (n: number) =>
  n >= 1_000_000
    ? `€${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000
    ? `€${(n / 1_000).toFixed(0)}k`
    : `€${n.toFixed(0)}`;

const TYPE_OPTIONS = ["new", "expansion", "renewal", "churn"];

function AddRevenueModal({ onClose }: { onClose: () => void }) {
  const create = useCreateRevenue();
  const [form, setForm] = useState<RevenueCreate>({
    arr: 0,
    date_closed: new Date().toISOString().slice(0, 10),
    type: "new",
    currency: "EUR",
  });
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.arr <= 0) { setError("ARR must be greater than 0"); return; }
    try {
      await create.mutateAsync(form);
      onClose();
    } catch {
      setError("Failed to create revenue record.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">Log Revenue</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">ARR (€)</label>
            <input
              type="number"
              step="any"
              min="0.01"
              className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={form.arr || ""}
              onChange={(e) => setForm({ ...form, arr: parseFloat(e.target.value) || 0 })}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Date Closed</label>
            <input
              type="date"
              className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={form.date_closed}
              onChange={(e) => setForm({ ...form, date_closed: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
            <select
              className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
            >
              {TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Currency</label>
            <input
              type="text"
              maxLength={10}
              className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Attribution (optional)</label>
            <input
              type="text"
              className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              value={form.attribution ?? ""}
              onChange={(e) => setForm({ ...form, attribution: e.target.value || undefined })}
            />
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-600 border rounded-md hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="px-4 py-2 text-sm bg-violet-600 text-white rounded-md hover:bg-violet-700 disabled:opacity-60"
            >
              {create.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Revenue() {
  const [showAdd, setShowAdd] = useState(false);
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);

  const filters = {
    page,
    page_size: 20,
    ...(typeFilter ? { type: typeFilter } : {}),
  };

  const { data: summary, isLoading: summaryLoading } = useRevenueSummary();
  const { data: records, isLoading: recordsLoading } = useRevenue(filters);
  const deleteRevenue = useDeleteRevenue();

  const trends = summary?.monthly_trends ?? [];

  return (
    <div className="p-6 space-y-6">
      {showAdd && <AddRevenueModal onClose={() => setShowAdd(false)} />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Revenue</h1>
          <p className="text-slate-500 text-sm mt-0.5">ARR records & monthly trends</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-violet-600 text-white text-sm rounded-md hover:bg-violet-700 transition"
        >
          <Plus className="w-4 h-4" />
          Log Revenue
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total ARR"
          value={summaryLoading ? "—" : fmt(summary?.total_arr ?? 0)}
          accent="green"
        />
        <KpiCard
          label="Total MRR"
          value={summaryLoading ? "—" : fmt(summary?.total_mrr ?? 0)}
          accent="blue"
        />
        <KpiCard
          label="Records"
          value={summaryLoading ? "—" : String(summary?.record_count ?? 0)}
          accent="default"
        />
        <KpiCard
          label="Currencies"
          value={summaryLoading ? "—" : String(Object.keys(summary?.arr_by_currency ?? {}).length)}
          sub={Object.keys(summary?.arr_by_currency ?? {}).join(", ")}
          accent="amber"
        />
      </div>

      {/* Trend chart */}
      <div className="bg-white rounded-lg border p-5">
        <h2 className="font-semibold text-slate-800 mb-4">Monthly ARR (12 months)</h2>
        {trends.length === 0 ? (
          <p className="text-slate-400 text-sm">No revenue records yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trends} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} width={56} />
              <Tooltip formatter={(v: number) => [`€${v.toLocaleString()}`, "ARR"]} />
              <Area type="monotone" dataKey="arr" stroke="#7c3aed" strokeWidth={2} fill="url(#revGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Records table */}
      <div className="bg-white rounded-lg border">
        <div className="px-5 py-4 border-b flex items-center justify-between">
          <h2 className="font-semibold text-slate-800">Records</h2>
          <select
            className="border rounded-md px-2 py-1 text-sm text-slate-700 focus:outline-none"
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          >
            <option value="">All types</option>
            {TYPE_OPTIONS.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wide border-b">
                <th className="px-5 py-3">Date</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3 text-right">ARR</th>
                <th className="px-5 py-3 text-right">MRR</th>
                <th className="px-5 py-3">Currency</th>
                <th className="px-5 py-3">Attribution</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {recordsLoading && (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-slate-400">Loading…</td>
                </tr>
              )}
              {!recordsLoading && (records?.items ?? []).length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-slate-400">No records found.</td>
                </tr>
              )}
              {(records?.items ?? []).map((r) => (
                <tr key={r.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="px-5 py-3 text-slate-700">{r.date_closed}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${
                      r.type === "new" ? "bg-emerald-100 text-emerald-700" :
                      r.type === "expansion" ? "bg-blue-100 text-blue-700" :
                      r.type === "renewal" ? "bg-violet-100 text-violet-700" :
                      "bg-red-100 text-red-700"
                    }`}>
                      {r.type}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right font-medium text-emerald-700">{fmt(r.arr)}</td>
                  <td className="px-5 py-3 text-right text-slate-600">{fmt(r.mrr)}</td>
                  <td className="px-5 py-3 text-slate-500">{r.currency}</td>
                  <td className="px-5 py-3 text-slate-400 text-xs">{r.attribution ?? "—"}</td>
                  <td className="px-5 py-3">
                    <button
                      onClick={() => deleteRevenue.mutate(r.id)}
                      className="text-red-400 hover:text-red-600 transition"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {(records?.pages ?? 0) > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t text-sm text-slate-600">
            <span>
              Page {records?.page} of {records?.pages} ({records?.total} total)
            </span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1 border rounded-md hover:bg-slate-50 disabled:opacity-40"
              >
                Prev
              </button>
              <button
                disabled={page >= (records?.pages ?? 1)}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 border rounded-md hover:bg-slate-50 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
