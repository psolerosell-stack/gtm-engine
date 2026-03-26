import { useState } from "react";
import { X } from "lucide-react";
import { useUpdateOpportunity } from "@/hooks/useOpportunities";
import { Opportunity } from "@/api/client";

interface UpdateStageModalProps {
  opportunity: Opportunity;
  onClose: () => void;
}

const STAGES = [
  "prospecting",
  "qualification",
  "discovery",
  "demo",
  "proposal",
  "negotiation",
  "closed_won",
  "closed_lost",
];

export function UpdateStageModal({ opportunity, onClose }: UpdateStageModalProps) {
  const [stage, setStage] = useState(opportunity.stage);
  const [closeReason, setCloseReason] = useState(opportunity.close_reason ?? "");
  const { mutateAsync, isPending } = useUpdateOpportunity(opportunity.id);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await mutateAsync({
      stage,
      close_reason: closeReason.trim() || undefined,
    });
    onClose();
  };

  const isClosing = stage === "closed_won" || stage === "closed_lost";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <div className="text-sm font-semibold text-gray-900">Update Stage</div>
            <div className="text-xs text-gray-500 mt-0.5">{opportunity.name}</div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Stage</label>
            <select
              value={stage}
              onChange={(e) => setStage(e.target.value)}
              className="w-full text-sm border border-gray-200 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>

          {isClosing && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Close reason <span className="text-gray-400">(optional)</span>
              </label>
              <input
                type="text"
                value={closeReason}
                onChange={(e) => setCloseReason(e.target.value)}
                placeholder="e.g. Budget, Timeline, Competitor"
                className="w-full text-sm border border-gray-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

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
              disabled={isPending || stage === opportunity.stage}
              className="flex-1 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-md transition-colors"
            >
              {isPending ? "Saving…" : "Update"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
