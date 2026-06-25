import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import {
  createColumnHelper, flexRender, getCoreRowModel,
  getSortedRowModel, SortingState, useReactTable,
} from "@tanstack/react-table";
import { LayoutList, Columns, Plus, ExternalLink } from "lucide-react";
import {
  DndContext, DragEndEvent, DragOverEvent, DragOverlay, DragStartEvent,
  PointerSensor, useSensor, useSensors,
} from "@dnd-kit/core";
import { useDroppable } from "@dnd-kit/core";
import { useDraggable } from "@dnd-kit/core";
import { useOpportunities, usePipelineSummary } from "@/hooks/useOpportunities";
import { usePipelineStages } from "@/hooks/useSettings";
import { StageBadge } from "@/components/StageBadge";
import { CreateOpportunityModal } from "@/components/CreateOpportunityModal";
import { Opportunity, opportunitiesApi } from "@/api/client";
import { formatCurrency } from "@/utils/format";
import { useQueryClient } from "@tanstack/react-query";

const FALLBACK_STAGE_ORDER = [
  "prospecting", "qualification", "discovery", "demo",
  "proposal", "negotiation", "closed_won", "closed_lost",
];

const FALLBACK_COLORS: Record<string, string> = {
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
    cell: (info) => <span className="font-medium text-white">{info.getValue()}</span>,
  }),
  col.accessor("account", {
    header: "Account",
    cell: (info) => <span className="text-white/60">{info.getValue()?.name ?? "—"}</span>,
  }),
  col.accessor("stage", {
    header: "Stage",
    cell: (info) => <StageBadge stage={info.getValue()} />,
  }),
  col.accessor("arr_value", {
    header: "ARR",
    cell: (info) => (
      <span className="text-white/80">
        {info.getValue() != null ? formatCurrency(info.getValue()!) : "—"}
      </span>
    ),
  }),
  col.accessor("close_date", {
    header: "Close Date",
    cell: (info) => <span className="text-white/60">{info.getValue() ?? "—"}</span>,
  }),
  col.accessor("owner", {
    header: "Owner",
    cell: (info) => <span className="text-white/60">{info.getValue() ?? "—"}</span>,
  }),
];

// ── Draggable Kanban card ─────────────────────────────────────────────────────

function DraggableCard({ opp, onOpen }: { opp: Opportunity; onOpen: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: opp.id });

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={`bg-navy-800 rounded-lg border border-white/10 p-3 cursor-grab active:cursor-grabbing transition-opacity ${
        isDragging ? "opacity-30" : "hover:border-white/20 hover:bg-navy-700"
      }`}
    >
      <CardContent opp={opp} onOpen={onOpen} />
    </div>
  );
}

function CardContent({ opp, onOpen }: { opp: Opportunity; onOpen?: () => void }) {
  return (
    <>
      <div className="flex items-start justify-between gap-1 mb-1">
        <div className="font-medium text-sm text-white truncate flex-1">{opp.name}</div>
        {onOpen && (
          <button
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => { e.stopPropagation(); onOpen(); }}
            className="text-white/20 hover:text-white/60 transition-colors shrink-0"
            title="Ver detalle"
          >
            <ExternalLink size={12} />
          </button>
        )}
      </div>
      {opp.account?.name && (
        <div className="text-xs text-white/40 mb-2 truncate">{opp.account.name}</div>
      )}
      <div className="flex items-center justify-between">
        {opp.arr_value != null && (
          <span className="text-xs font-semibold text-accent-green">
            {formatCurrency(opp.arr_value)}
          </span>
        )}
        {opp.close_date && (
          <span className="text-xs text-white/40">
            {new Date(opp.close_date).toLocaleDateString("es-ES", { month: "short", day: "numeric" })}
          </span>
        )}
      </div>
      {opp.owner && (
        <div className="text-xs text-white/40 mt-1 truncate">👤 {opp.owner}</div>
      )}
    </>
  );
}

// ── Droppable column ──────────────────────────────────────────────────────────

function KanbanColumn({
  stage,
  cards,
  color,
  isLoading,
  isOver,
  onCardOpen,
}: {
  stage: { slug: string; name: string };
  cards: Opportunity[];
  color: string;
  isLoading: boolean;
  isOver: boolean;
  onCardOpen: (id: string) => void;
}) {
  const { setNodeRef } = useDroppable({ id: stage.slug });
  const stageARR = cards.reduce((sum, o) => sum + (o.arr_value ?? 0), 0);

  return (
    <div className="w-60 flex flex-col shrink-0">
      <div
        className="flex items-center justify-between px-3 py-2 rounded-t-lg text-white text-sm font-medium"
        style={{ backgroundColor: color }}
      >
        <span className="truncate">{stage.name}</span>
        <span className="ml-2 bg-white/20 rounded-full px-2 py-0.5 text-xs font-bold shrink-0">
          {cards.length}
        </span>
      </div>
      <div
        className="px-3 py-1 text-xs font-medium"
        style={{ backgroundColor: color + "22", color }}
      >
        {stageARR > 0 ? formatCurrency(stageARR) : "—"}
      </div>
      <div
        ref={setNodeRef}
        className={`flex-1 rounded-b-lg border border-white/10 border-t-0 p-2 space-y-2 min-h-[120px] transition-colors ${
          isOver ? "bg-accent-blue/10" : "bg-navy-900"
        }`}
      >
        {isLoading ? (
          <div className="text-xs text-white/30 text-center pt-4">Loading…</div>
        ) : cards.length === 0 ? (
          <div className="text-xs text-white/20 text-center pt-4">No deals</div>
        ) : (
          cards.map((opp) => <DraggableCard key={opp.id} opp={opp} onOpen={() => onCardOpen(opp.id)} />)
        )}
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function PipelineReview() {
  const navigate = useNavigate();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [stageFilter, setStageFilter] = useState<string>("");
  const [view, setView] = useState<"list" | "kanban">("list");
  const [showCreate, setShowCreate] = useState(false);
  const [activeOpp, setActiveOpp] = useState<Opportunity | null>(null);
  const [overColumn, setOverColumn] = useState<string | null>(null);

  const { data: opps, isLoading } = useOpportunities({
    stage: view === "list" ? (stageFilter || undefined) : undefined,
    page_size: 100,
  });

  const { data: summary } = usePipelineSummary();
  const { data: configuredStages = [] } = usePipelineStages();
  const qc = useQueryClient();

  const stages = configuredStages.length > 0
    ? configuredStages.filter((s) => s.is_active)
    : FALLBACK_STAGE_ORDER.map((slug) => ({
        slug,
        name: slug.replace(/_/g, " "),
        color: FALLBACK_COLORS[slug] ?? "#94a3b8",
        is_active: true,
      }));

  const stageColorMap = Object.fromEntries(
    stages.map((s) => [s.slug, (s as { color?: string }).color ?? FALLBACK_COLORS[s.slug] ?? "#94a3b8"])
  );

  const chartData = stages
    .map((s) => ({
      stage: s.name,
      count: summary?.[s.slug]?.count ?? 0,
      arr: summary?.[s.slug]?.total_arr ?? 0,
      key: s.slug,
    }))
    .filter((d) => d.count > 0);

  const totalARR = Object.values(summary ?? {}).reduce((a, b) => a + b.total_arr, 0);
  const openDeals = Object.entries(summary ?? {})
    .filter(([s]) => !stages.find((st) => st.slug === s && (st as { is_won?: boolean }).is_won))
    .filter(([s]) => !stages.find((st) => st.slug === s && (st as { is_lost?: boolean }).is_lost))
    .reduce((a, [, v]) => a + v.count, 0);

  const table = useReactTable({
    data: opps?.items ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const oppsByStage: Record<string, Opportunity[]> = {};
  for (const s of stages) {
    oppsByStage[s.slug] = (opps?.items ?? []).filter((o) => o.stage === s.slug);
  }

  // ── DnD handlers ─────────────────────────────────────────────────────────────

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  function handleDragStart(event: DragStartEvent) {
    const opp = (opps?.items ?? []).find((o) => o.id === event.active.id);
    setActiveOpp(opp ?? null);
  }

  function handleDragOver(event: DragOverEvent) {
    setOverColumn(event.over ? String(event.over.id) : null);
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveOpp(null);
    setOverColumn(null);

    if (!over) return;
    const newStage = String(over.id);
    const opp = (opps?.items ?? []).find((o) => o.id === active.id);
    if (!opp || opp.stage === newStage) return;

    await opportunitiesApi.update(opp.id, { stage: newStage });
    qc.invalidateQueries({ queryKey: ["opportunities"] });
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Pipeline Review</h1>
          <p className="text-sm text-white/50">All active opportunities across stages</p>
        </div>
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex items-center rounded-lg border border-white/10 overflow-hidden">
            <button
              onClick={() => setView("list")}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm transition-colors ${
                view === "list" ? "bg-accent-blue text-white" : "bg-navy-800 text-white/60 hover:bg-white/5 hover:text-white"
              }`}
            >
              <LayoutList size={14} /> Lista
            </button>
            <button
              onClick={() => setView("kanban")}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm transition-colors ${
                view === "kanban" ? "bg-accent-blue text-white" : "bg-navy-800 text-white/60 hover:bg-white/5 hover:text-white"
              }`}
            >
              <Columns size={14} /> Kanban
            </button>
          </div>
          {/* New deal */}
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-accent-blue rounded-lg hover:bg-blue-600 transition-colors"
          >
            <Plus size={14} /> New Deal
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Open Deals", value: openDeals },
          { label: "Total Pipeline ARR", value: formatCurrency(totalARR) },
          { label: "Won ARR", value: formatCurrency(summary?.closed_won?.total_arr ?? 0) },
          { label: "Avg Deal Size", value: formatCurrency(openDeals > 0 ? totalARR / openDeals : 0) },
        ].map(({ label, value }) => (
          <div key={label} className="bg-navy-800 rounded-lg border border-white/10 p-4">
            <div className="text-xs text-white/40 uppercase tracking-wide">{label}</div>
            <div className="text-2xl font-bold text-white mt-1">{value}</div>
          </div>
        ))}
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="bg-navy-800 rounded-lg border border-white/10 p-4">
          <div className="text-sm font-medium text-white/70 mb-3">Deal distribution by stage</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="stage" tick={{ fontSize: 11, fill: "#8892A4" }} />
              <YAxis tick={{ fontSize: 11, fill: "#8892A4" }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1A2340", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}
                labelStyle={{ color: "#fff" }}
                itemStyle={{ color: "#8892A4" }}
                formatter={(val: number, name: string) =>
                  name === "arr" ? [formatCurrency(val), "ARR"] : [val, "Deals"]
                }
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={entry.key} fill={stageColorMap[entry.key] ?? "#94a3b8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── List view ── */}
      {view === "list" && (
        <>
          <div className="flex items-center gap-3">
            <label className="text-sm text-white/50">Filter by stage:</label>
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              className="text-sm bg-navy-800 border border-white/10 rounded-lg px-3 py-1.5 text-white focus:outline-none focus:ring-2 focus:ring-accent-blue"
            >
              <option value="">All stages</option>
              {stages.map((s) => (
                <option key={s.slug} value={s.slug}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="bg-navy-800 rounded-lg border border-white/10 overflow-hidden">
            {isLoading ? (
              <div className="p-8 text-center text-sm text-white/40">Loading opportunities…</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-navy-900 border-b border-white/10">
                  {table.getHeaderGroups().map((hg) => (
                    <tr key={hg.id}>
                      {hg.headers.map((header) => (
                        <th
                          key={header.id}
                          onClick={header.column.getToggleSortingHandler()}
                          className="px-4 py-3 text-left text-xs font-medium text-white/40 uppercase tracking-wide cursor-pointer select-none hover:text-white/70 transition-colors"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {{ asc: " ↑", desc: " ↓" }[header.column.getIsSorted() as string] ?? ""}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody className="divide-y divide-white/5">
                  {table.getRowModel().rows.length === 0 ? (
                    <tr>
                      <td colSpan={columns.length} className="px-4 py-8 text-center text-white/40">
                        No opportunities found
                      </td>
                    </tr>
                  ) : (
                    table.getRowModel().rows.map((row) => (
                      <tr
                        key={row.id}
                        className="hover:bg-white/5 transition-colors cursor-pointer"
                        onClick={() => navigate(`/pipeline/${row.original.id}`)}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id} className="px-4 py-3">
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
        </>
      )}

      {/* ── Kanban view ── */}
      {view === "kanban" && (
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <div className="overflow-x-auto pb-4">
            <div className="flex gap-4 min-w-max">
              {stages.map((stage) => {
                const color = (stage as { color?: string }).color ?? FALLBACK_COLORS[stage.slug] ?? "#94a3b8";
                return (
                  <KanbanColumn
                    key={stage.slug}
                    stage={stage}
                    cards={oppsByStage[stage.slug] ?? []}
                    color={color}
                    isLoading={isLoading}
                    isOver={overColumn === stage.slug}
                    onCardOpen={(id) => navigate(`/pipeline/${id}`)}
                  />
                );
              })}
            </div>
          </div>

          {/* Drag overlay — ghost card while dragging */}
          <DragOverlay>
            {activeOpp && (
              <div className="bg-navy-800 border border-white/20 rounded-lg p-3 shadow-2xl w-56 rotate-1 opacity-90">
                <CardContent opp={activeOpp} />
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}

      {/* Create modal */}
      {showCreate && <CreateOpportunityModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
