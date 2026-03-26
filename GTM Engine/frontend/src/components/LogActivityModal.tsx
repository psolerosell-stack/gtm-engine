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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <div className="text-sm font-semibold text-gray-900">Log Activity</div>
            {entityName && (
              <div className="text-xs text-gray-500 mt-0.5">{entityName}</div>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full text-sm border border-gray-200 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {ACTIVITY_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="What happened?"
              className="w-full text-sm border border-gray-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Outcome <span className="text-gray-400">(optional)</span>
            </label>
            <input
              type="text"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              placeholder="e.g. Interested, follow up next week"
              className="w-full text-sm border border-gray-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 text-sm border border-gray-200 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !notes.trim()}
              className="flex-1 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-md transition-colors"
            >
              {isPending ? "Saving…" : "Log Activity"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
