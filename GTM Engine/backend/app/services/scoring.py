"""
ScoringEngine — Layer 2 ICP scoring with dynamic weight versioning.

All scoring logic lives here. PartnerService delegates to this class,
which loads the active ScoringWeightVersion from the DB (or falls back
to DEFAULT_WEIGHTS if no active version exists).
"""
import json
from typing import Any, Dict, Optional, Tuple

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import ScoringWeightVersion
from app.models.account import Account
from app.models.partner import Partner, PartnerTier

logger = structlog.get_logger(__name__)

# ── Default weights (sum = 1.0) ──────────────────────────────────────────────

DEFAULT_WEIGHTS: Dict[str, float] = {
    "erp_ecosystem_fit": 0.20,
    "partner_type_match": 0.15,
    "capacity_score": 0.15,
    "geography_match": 0.10,
    "vertical_fit": 0.10,
    "company_size": 0.10,
    "arr_potential": 0.10,
    "activation_velocity": 0.10,
}

# ── Lookup tables ─────────────────────────────────────────────────────────────

ERP_SCORES: Dict[str, float] = {
    "business_central": 10,
    "navision": 10,
    "sage_200": 9,
    "sage_x3": 9,
    "sap_b1": 8,
    "netsuite": 8,
    "holded": 7,
    "other": 5,
}

PARTNER_TYPE_SCORES: Dict[str, float] = {
    "OEM": 10,
    "VAR+": 9,
    "VAR": 8,
    "Alliance": 7,
    "Referral": 6,
}

GEOGRAPHY_SCORES: Dict[str, float] = {
    "spain": 10,
    "españa": 10,
    "es": 10,
}
LATAM_COUNTRIES = {"mexico", "colombia", "argentina", "chile", "peru", "latam"}

VERTICAL_SCORES: Dict[str, float] = {
    "manufacturing": 10,
    "distribution": 10,
    "wholesale": 9,
    "logistics": 8,
    "services": 7,
}


# ── Pure scoring functions ────────────────────────────────────────────────────


def compute_icp_score(
    partner: Partner,
    account: Optional[Account],
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute weighted ICP score (0–100) for a partner.
    Returns (score, breakdown_dict).
    """
    w = weights or DEFAULT_WEIGHTS
    breakdown: Dict[str, Any] = {}

    # 1. ERP ecosystem fit
    erp_raw = 5.0
    erp_label = "unknown"
    if account and account.erp_ecosystem:
        key = account.erp_ecosystem.lower().replace(" ", "_").replace("-", "_")
        erp_raw = ERP_SCORES.get(key, 5.0)
        erp_label = account.erp_ecosystem
    breakdown["erp_ecosystem_fit"] = {
        "weight": w["erp_ecosystem_fit"],
        "raw": erp_raw,
        "weighted": round(erp_raw * w["erp_ecosystem_fit"], 4),
        "label": erp_label,
    }

    # 2. Partner type match
    type_raw = PARTNER_TYPE_SCORES.get(partner.type, 5.0)
    breakdown["partner_type_match"] = {
        "weight": w["partner_type_match"],
        "raw": type_raw,
        "weighted": round(type_raw * w["partner_type_match"], 4),
        "label": partner.type,
    }

    # 3. Capacity score (sum of four dimensions, each 0–2.5 → max 10)
    capacity_sum = (
        partner.capacity_commercial
        + partner.capacity_functional
        + partner.capacity_technical
        + partner.capacity_integration
    )
    capacity_raw = min(capacity_sum, 10.0)
    breakdown["capacity_score"] = {
        "weight": w["capacity_score"],
        "raw": round(capacity_raw, 2),
        "weighted": round(capacity_raw * w["capacity_score"], 4),
        "label": (
            f"commercial={partner.capacity_commercial} functional={partner.capacity_functional} "
            f"technical={partner.capacity_technical} integration={partner.capacity_integration}"
        ),
    }

    # 4. Geography match
    geo_raw = 5.0
    geo_label = partner.geography or "unknown"
    if partner.geography:
        geo_lower = partner.geography.lower()
        if geo_lower in GEOGRAPHY_SCORES:
            geo_raw = 10.0
        elif geo_lower in LATAM_COUNTRIES or "latam" in geo_lower:
            geo_raw = 7.0
        else:
            geo_raw = 5.0
    breakdown["geography_match"] = {
        "weight": w["geography_match"],
        "raw": geo_raw,
        "weighted": round(geo_raw * w["geography_match"], 4),
        "label": geo_label,
    }

    # 5. Vertical fit
    vert_raw = 5.0
    vert_label = partner.vertical or "unknown"
    if partner.vertical:
        vert_lower = partner.vertical.lower()
        vert_raw = next(
            (v for k, v in VERTICAL_SCORES.items() if k in vert_lower),
            5.0,
        )
    breakdown["vertical_fit"] = {
        "weight": w["vertical_fit"],
        "raw": vert_raw,
        "weighted": round(vert_raw * w["vertical_fit"], 4),
        "label": vert_label,
    }

    # 6. Company size
    size_raw = 5.0
    size_label = "unknown"
    if account and account.size:
        size = account.size
        size_label = str(size)
        if 10 <= size <= 50:
            size_raw = 10.0
        elif 5 <= size < 10:
            size_raw = 8.0
        else:
            size_raw = 6.0
    breakdown["company_size"] = {
        "weight": w["company_size"],
        "raw": size_raw,
        "weighted": round(size_raw * w["company_size"], 4),
        "label": size_label,
    }

    # 7. ARR potential
    arr_raw = 4.0
    arr_label = "unknown"
    if partner.arr_potential is not None:
        arr_label = f"{partner.arr_potential:.0f}"
        if partner.arr_potential >= 50000:
            arr_raw = 10.0
        elif partner.arr_potential >= 20000:
            arr_raw = 7.0
        else:
            arr_raw = 4.0
    breakdown["arr_potential"] = {
        "weight": w["arr_potential"],
        "raw": arr_raw,
        "weighted": round(arr_raw * w["arr_potential"], 4),
        "label": arr_label,
    }

    # 8. Activation velocity
    vel_raw = 4.0
    vel_label = "unknown"
    if partner.activation_velocity is not None:
        vel_label = f"{partner.activation_velocity} days"
        if partner.activation_velocity < 30:
            vel_raw = 10.0
        elif partner.activation_velocity <= 90:
            vel_raw = 7.0
        else:
            vel_raw = 4.0
    breakdown["activation_velocity"] = {
        "weight": w["activation_velocity"],
        "raw": vel_raw,
        "weighted": round(vel_raw * w["activation_velocity"], 4),
        "label": vel_label,
    }

    # Total (sum of weighted values × 10 to normalise to 0–100)
    total = sum(dim["weighted"] for dim in breakdown.values()) * 10
    total = min(round(total, 2), 100.0)

    return total, breakdown


def tier_from_score(score: float) -> str:
    if score >= 85:
        return PartnerTier.platinum
    if score >= 70:
        return PartnerTier.gold
    if score >= 50:
        return PartnerTier.silver
    return PartnerTier.bronze


# ── ScoringEngine class ───────────────────────────────────────────────────────


class ScoringEngine:
    """
    Stateless scoring engine that optionally loads dynamic weights from DB.

    Usage:
        engine = ScoringEngine()
        weights = await engine.load_active_weights(db)
        score, breakdown = engine.score(partner, account, weights)
        tier = engine.tier(score)
    """

    def __init__(self) -> None:
        self._cached_weights: Optional[Dict[str, float]] = None
        self._cached_version_id: Optional[str] = None

    async def load_active_weights(
        self, db: AsyncSession
    ) -> Dict[str, float]:
        """
        Load the active ScoringWeightVersion from DB.
        Falls back to DEFAULT_WEIGHTS if none is active.
        """
        result = await db.execute(
            select(ScoringWeightVersion)
            .where(ScoringWeightVersion.is_active.is_(True))
            .order_by(ScoringWeightVersion.version.desc())
            .limit(1)
        )
        version = result.scalar_one_or_none()

        if version is None:
            logger.debug("scoring_weights_default", reason="no_active_version")
            return DEFAULT_WEIGHTS

        try:
            weights = json.loads(version.weights)
            logger.debug(
                "scoring_weights_loaded",
                version=version.version,
                version_id=str(version.id),
            )
            return weights
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "scoring_weights_invalid_json",
                version_id=str(version.id),
            )
            return DEFAULT_WEIGHTS

    def score(
        self,
        partner: Partner,
        account: Optional[Account],
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """Compute ICP score. Pass weights from load_active_weights() or omit for defaults."""
        return compute_icp_score(partner, account, weights)

    def tier(self, score: float) -> str:
        return tier_from_score(score)


# Module-level singleton — import this in services
engine = ScoringEngine()
