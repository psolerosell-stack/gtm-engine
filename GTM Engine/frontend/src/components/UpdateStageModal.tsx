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

const INPUT = "w-full bg-navy-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-accent-blue focus:border-transparent";
const LABEL = "block text-xs font-medium text-white/50 mb-1";

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-navy-800 border border-white/10 rounded-xl shadow-2xl w-full max-w-sm mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div>
            <div className="text-sm font-semibold text-white">Update Stage</div>
            <div className="text-xs text-white/40 mt-0.5">{opportunity.name}</div>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          <div>
            <label className={LABEL}>Stage</label>
            <select
              value={stage}
              onChange={(e) => setStage(e.target.value)}
              className={INPUT}
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
              <label className={LABEL}>
                Close reason <span className="text-white/30">(optional)</span>
              </label>
              <input
                type="text"
                value={closeReason}
                onChange={(e) => setCloseReason(e.target.value)}
                placeholder="e.g. Budget, Timeline, Competitor"
                className={INPUT}
              />
            </div>
          )}

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
              disabled={isPending || stage === opportunity.stage}
              className="flex-1 text-sm bg-accent-blue hover:bg-blue-600 disabled:opacity-50 text-white px-4 py-2 rounded-lg transition-colors"
            >
              {isPending ? "Saving…" : "Update"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
