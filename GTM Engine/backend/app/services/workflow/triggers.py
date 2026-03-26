"""
Trigger type definitions and condition evaluation — Layer 4.

A trigger fires when something happens in the system. The engine evaluates
whether an active workflow matches the trigger and its conditions.
"""
from enum import Enum
from typing import Any, Dict


class TriggerType(str, Enum):
    partner_created = "partner_created"
    score_threshold_reached = "score_threshold_reached"   # config: {threshold: 70}
    opportunity_stage_changed = "opportunity_stage_changed"  # config: {stage: "closed_won"} or any
    partner_inactive = "partner_inactive"                 # config: {days: 14}
    deal_closed_won = "deal_closed_won"
    deal_closed_lost = "deal_closed_lost"
    lead_from_partner = "lead_from_partner"
    onboarding_completed = "onboarding_completed"
    partner_not_converted = "partner_not_converted"       # config: {days: 60}


def evaluate_trigger_conditions(
    trigger_type: TriggerType,
    trigger_config: Dict[str, Any],
    trigger_data: Dict[str, Any],
) -> bool:
    """
    Returns True if the workflow's trigger_config conditions are satisfied
    by the event's trigger_data.

    trigger_config = workflow-level configuration (e.g. {"threshold": 70})
    trigger_data   = event payload (e.g. {"score": 75, "previous_score": 65})
    """
    if trigger_type == TriggerType.score_threshold_reached:
        threshold = float(trigger_config.get("threshold", 70))
        score = float(trigger_data.get("score", 0))
        prev_score = float(trigger_data.get("previous_score", 0))
        # Only fire when score crosses the threshold upwards
        return score >= threshold and prev_score < threshold

    if trigger_type == TriggerType.opportunity_stage_changed:
        # If config specifies a target stage, only match that stage
        target_stage = trigger_config.get("stage")
        if target_stage:
            return trigger_data.get("new_stage") == target_stage
        return True  # any stage change

    if trigger_type == TriggerType.partner_inactive:
        days_threshold = int(trigger_config.get("days", 14))
        inactive_days = int(trigger_data.get("inactive_days", 0))
        return inactive_days >= days_threshold

    if trigger_type == TriggerType.partner_not_converted:
        days_threshold = int(trigger_config.get("days", 60))
        days_pending = int(trigger_data.get("days_pending", 0))
        return days_pending >= days_threshold

    # All other triggers fire unconditionally when their type matches
    return True
