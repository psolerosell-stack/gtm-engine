"""
The 9 system workflow definitions — Layer 4.

These are seeded once at startup (or via seed command). They cannot be deleted
(is_system=True), only deactivated.
"""
from typing import List, Dict, Any


SYSTEM_WORKFLOWS: List[Dict[str, Any]] = [
    # ── 1. Partner Created ─────────────────────────────────────────────────────
    {
        "name": "Partner Created: Onboarding Kickoff",
        "description": "When a new partner is created, create HubSpot company, onboarding task, and log start note.",
        "trigger_type": "partner_created",
        "trigger_config": {},
        "actions": [
            {
                "sequence": 1,
                "type": "hubspot_create_company",
                "config": {},
            },
            {
                "sequence": 2,
                "type": "create_task",
                "config": {
                    "title": "Complete onboarding checklist for new partner",
                    "owner": "system",
                },
            },
            {
                "sequence": 3,
                "type": "log_activity",
                "config": {
                    "activity_type": "note",
                    "notes": "Partner created. Onboarding sequence started.",
                },
            },
        ],
    },

    # ── 2. Score Threshold >70 ─────────────────────────────────────────────────
    {
        "name": "ICP Score Threshold: Activation Alert",
        "description": "When a partner crosses ICP score 70, notify on Slack and create activation task.",
        "trigger_type": "score_threshold_reached",
        "trigger_config": {"threshold": 70},
        "actions": [
            {
                "sequence": 1,
                "type": "slack_notify",
                "config": {
                    "message": "🎯 Partner ICP score crossed 70 — score={score:.1f}, tier upgraded to {tier}. Time to activate!",
                },
            },
            {
                "sequence": 2,
                "type": "create_task",
                "config": {
                    "title": "Activate partner — ICP threshold reached (score={score:.1f})",
                },
            },
            {
                "sequence": 3,
                "type": "generate_ai_intelligence",
                "config": {},
            },
        ],
    },

    # ── 3. Opportunity Stage Changed ───────────────────────────────────────────
    {
        "name": "Opportunity Stage Change: Follow-up",
        "description": "When an opportunity stage changes, update HubSpot deal, create follow-up task.",
        "trigger_type": "opportunity_stage_changed",
        "trigger_config": {},
        "actions": [
            {
                "sequence": 1,
                "type": "hubspot_update_deal",
                "config": {},
            },
            {
                "sequence": 2,
                "type": "create_task",
                "config": {
                    "title": "Follow up — opportunity moved to {new_stage}",
                },
            },
            {
                "sequence": 3,
                "type": "log_activity",
                "config": {
                    "activity_type": "note",
                    "notes": "Stage changed from {previous_stage} to {new_stage}.",
                },
            },
        ],
    },

    # ── 4. Partner Inactive 14 Days ────────────────────────────────────────────
    {
        "name": "Partner Inactive: Re-engagement Alert",
        "description": "When a partner has no activity for 14 days, create re-engagement task and alert on Slack.",
        "trigger_type": "partner_inactive",
        "trigger_config": {"days": 14},
        "actions": [
            {
                "sequence": 1,
                "type": "create_task",
                "config": {
                    "title": "Re-engage partner — no activity for {inactive_days} days",
                },
            },
            {
                "sequence": 2,
                "type": "slack_notify",
                "config": {
                    "message": "⚠️ Partner has been inactive for {inactive_days} days. Re-engagement task created.",
                },
            },
        ],
    },

    # ── 5. Deal Closed Won ─────────────────────────────────────────────────────
    {
        "name": "Deal Closed-Won: Revenue Attribution",
        "description": "When a deal closes won, create revenue record and recalculate partner score.",
        "trigger_type": "deal_closed_won",
        "trigger_config": {},
        "actions": [
            {
                "sequence": 1,
                "type": "create_revenue_record",
                "config": {},
            },
            {
                "sequence": 2,
                "type": "score_recalculate",
                "config": {},
            },
            {
                "sequence": 3,
                "type": "log_activity",
                "config": {
                    "activity_type": "note",
                    "notes": "Deal closed-won. Revenue record created. Score recalculated.",
                },
            },
        ],
    },

    # ── 6. Deal Closed Lost ────────────────────────────────────────────────────
    {
        "name": "Deal Closed-Lost: Post-mortem",
        "description": "When a deal closes lost, log reason, schedule post-mortem, and adjust scoring.",
        "trigger_type": "deal_closed_lost",
        "trigger_config": {},
        "actions": [
            {
                "sequence": 1,
                "type": "log_activity",
                "config": {
                    "activity_type": "note",
                    "notes": "Deal closed-lost. Reason: {close_reason}",
                },
            },
            {
                "sequence": 2,
                "type": "create_task",
                "config": {
                    "title": "Schedule post-mortem for closed-lost deal: {opportunity_name}",
                },
            },
            {
                "sequence": 3,
                "type": "score_recalculate",
                "config": {},
            },
        ],
    },

    # ── 7. New Lead from Partner ───────────────────────────────────────────────
    {
        "name": "Lead from Partner: Referral Tracking",
        "description": "When a lead is referred by a partner, log activity and create follow-up task.",
        "trigger_type": "lead_from_partner",
        "trigger_config": {},
        "actions": [
            {
                "sequence": 1,
                "type": "log_activity",
                "config": {
                    "activity_type": "note",
                    "notes": "New lead referred by partner. Referral tracking started.",
                },
            },
            {
                "sequence": 2,
                "type": "create_task",
                "config": {
                    "title": "Qualify lead referred by partner and create opportunity",
                },
            },
        ],
    },

    # ── 8. Onboarding Completed ────────────────────────────────────────────────
    {
        "name": "Onboarding Completed: Activate Partner",
        "description": "When onboarding is marked complete, set partner status to active and notify Slack.",
        "trigger_type": "onboarding_completed",
        "trigger_config": {},
        "actions": [
            {
                "sequence": 1,
                "type": "update_partner_field",
                "config": {
                    "fields": {"status": "active"},
                },
            },
            {
                "sequence": 2,
                "type": "log_activity",
                "config": {
                    "activity_type": "onboarding",
                    "notes": "Onboarding completed. Partner status set to active.",
                },
            },
            {
                "sequence": 3,
                "type": "slack_notify",
                "config": {
                    "message": "✅ Partner onboarding completed! Partner is now active.",
                },
            },
        ],
    },

    # ── 9. Partner Not Converted After 60 Days ─────────────────────────────────
    {
        "name": "Partner Not Converted: Escalation",
        "description": "When a partner remains in 'pending' for 60 days, flag for review and escalate.",
        "trigger_type": "partner_not_converted",
        "trigger_config": {"days": 60},
        "actions": [
            {
                "sequence": 1,
                "type": "create_task",
                "config": {
                    "title": "Review partner — not converted after {days_pending} days",
                },
            },
            {
                "sequence": 2,
                "type": "create_task",
                "config": {
                    "title": "Create enablement plan for stalled partner",
                },
            },
            {
                "sequence": 3,
                "type": "slack_notify",
                "config": {
                    "message": "🚨 Escalation: Partner has not been converted after {days_pending} days. Review required.",
                },
            },
        ],
    },
]
