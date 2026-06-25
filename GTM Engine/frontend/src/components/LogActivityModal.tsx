import { useState } from "react";
import { X } from "lucide-react";
import { useCreateActivity } from "@/hooks/useActivities";

interface LogActivityModalProps {
  entityType: string;
  entityId: string;
  entityName?: string;
  onClose: () => void;
}

const ACTIVITY_TYPES = [
  { value: "note", label: "Note" },
  { value: "call", label: "Call" },
  { value: "email", label: "Email" },
  { value: "meeting", label: "Meeting" },
  { value: "task", label: "Task" },
  { value: "demo", label: "Demo" },
  { value: "onboarding", label: "Onboarding" },
];

const INPUT = "w-full bg-navy-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-accent-blue focus:border-transparent";
const LABEL = "block text-xs font-medium text-white/50 mb-1";

export function LogActivityModal({
  entityType,
  entityId,
  entityName,
  onClose,
}: LogActivityModalProps) {
  const [type, setType] = useState("note");
  const [notes, setNotes] = useState("");
  const [outcome, setOutcome] = useState("");
  const { mutateAsync, isPending } = useCreateActivity();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!notes.trim()) return;
    await mutateAsync({
      entity_type: entityType,
      entity_id: entityId,
      type,
      notes: notes.trim(),
      outcome: outcome.trim() || undefined,
      date: new Date().toISOString(),
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-navy-800 border border-white/10 rounded-xl shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div>
            <div className="text-sm font-semibold text-white">Log Activity</div>
            {entityName && (
              <div className="text-xs text-white/40 mt-0.5">{entityName}</div>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          <div>
            <label className={LABEL}>Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className={INPUT}
            >
              {ACTIVITY_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className={LABEL}>Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="What happened?"
              className={INPUT + " resize-none"}
              required
            />
          </div>

          <div>
            <label className={LABEL}>
              Outcome <span className="text-white/30">(optional)</span>
            </label>
            <input
              type="text"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              placeholder="e.g. Interested, follow up next week"
              className={INPUT}
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 text-sm border border-white/10 text-white/60 hover:text-white px-4 py-2 rounded-lg hover:bg-white/5 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !notes.trim()}
              className="flex-1 text-sm bg-accent-blue hover:bg-blue-600 disabled:opacity-50 text-white px-4 py-2 rounded-lg transition-colors"
            >
              {isPending ? "Saving…" : "Log Activity"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
