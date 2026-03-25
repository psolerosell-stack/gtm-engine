"""
Layer 2 — ICP Scoring Engine tests.

Covers:
  - compute_icp_score() with various partner/account inputs
  - tier_from_score()
  - ScoringEngine.load_active_weights() (DB-backed, fallback to defaults)
  - Weight versioning API (create, list, activate)
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.services.scoring import (
    DEFAULT_WEIGHTS,
    ScoringEngine,
    compute_icp_score,
    tier_from_score,
)


# ── Unit tests — pure scoring functions ──────────────────────────────────────


def _make_partner(**kwargs):
    """Build a minimal mock partner."""
    p = MagicMock()
    p.type = kwargs.get("type", "VAR")
    p.capacity_commercial = kwargs.get("capacity_commercial", 0.0)
    p.capacity_functional = kwargs.get("capacity_functional", 0.0)
    p.capacity_technical = kwargs.get("capacity_technical", 0.0)
    p.capacity_integration = kwargs.get("capacity_integration", 0.0)
    p.geography = kwargs.get("geography", None)
    p.vertical = kwargs.get("vertical", None)
    p.arr_potential = kwargs.get("arr_potential", None)
    p.activation_velocity = kwargs.get("activation_velocity", None)
    return p


def _make_account(**kwargs):
    a = MagicMock()
    a.erp_ecosystem = kwargs.get("erp_ecosystem", None)
    a.size = kwargs.get("size", None)
    return a


def test_compute_icp_score_minimum():
    """Partner with no data scores low but not zero."""
    partner = _make_partner()
    score, breakdown = compute_icp_score(partner, account=None)
    assert 0 <= score <= 100
    assert "erp_ecosystem_fit" in breakdown
    assert "partner_type_match" in breakdown
    assert len(breakdown) == 8


def test_compute_icp_score_high_fit():
    """Top-tier partner should score >= 70."""
    partner = _make_partner(
        type="VAR+",
        capacity_commercial=2.5,
        capacity_functional=2.5,
        capacity_technical=2.5,
        capacity_integration=2.5,
        geography="Spain",
        vertical="Manufacturing",
        arr_potential=60000,
        activation_velocity=20,
    )
    account = _make_account(erp_ecosystem="sage_200", size=30)
    score, breakdown = compute_icp_score(partner, account)
    assert score >= 70


def test_compute_icp_score_oem_bc():
    """OEM partner on Business Central should get top ERP score."""
    partner = _make_partner(type="OEM")
    account = _make_account(erp_ecosystem="business_central")
    _, breakdown = compute_icp_score(partner, account)
    assert breakdown["erp_ecosystem_fit"]["raw"] == 10
    assert breakdown["partner_type_match"]["raw"] == 10


def test_compute_icp_score_latam():
    """LATAM geography should score 7."""
    partner = _make_partner(geography="Mexico")
    _, breakdown = compute_icp_score(partner, None)
    assert breakdown["geography_match"]["raw"] == 7.0


def test_compute_icp_score_spain():
    """Spain geography should score 10."""
    partner = _make_partner(geography="Spain")
    _, breakdown = compute_icp_score(partner, None)
    assert breakdown["geography_match"]["raw"] == 10.0


def test_compute_icp_score_fast_velocity():
    """Activation velocity < 30 days → raw = 10."""
    partner = _make_partner(activation_velocity=15)
    _, breakdown = compute_icp_score(partner, None)
    assert breakdown["activation_velocity"]["raw"] == 10.0


def test_compute_icp_score_slow_velocity():
    """Activation velocity > 90 days → raw = 4."""
    partner = _make_partner(activation_velocity=120)
    _, breakdown = compute_icp_score(partner, None)
    assert breakdown["activation_velocity"]["raw"] == 4.0


def test_compute_icp_score_arr_thresholds():
    partner_low = _make_partner(arr_potential=5000)
    partner_mid = _make_partner(arr_potential=30000)
    partner_high = _make_partner(arr_potential=75000)

    _, bd_low = compute_icp_score(partner_low, None)
    _, bd_mid = compute_icp_score(partner_mid, None)
    _, bd_high = compute_icp_score(partner_high, None)

    assert bd_low["arr_potential"]["raw"] == 4.0
    assert bd_mid["arr_potential"]["raw"] == 7.0
    assert bd_high["arr_potential"]["raw"] == 10.0


def test_compute_icp_score_custom_weights():
    """Custom weights that put full weight on erp_ecosystem_fit."""
    custom = {k: 0.0 for k in DEFAULT_WEIGHTS}
    custom["erp_ecosystem_fit"] = 1.0
    partner = _make_partner(type="VAR")
    account = _make_account(erp_ecosystem="sage_200")  # raw = 9

    score, breakdown = compute_icp_score(partner, account, weights=custom)
    # total = 9 * 1.0 * 10 = 90
    assert score == pytest.approx(90.0, abs=0.1)


def test_compute_icp_score_capped_at_100():
    """Score should never exceed 100."""
    partner = _make_partner(
        type="OEM",
        capacity_commercial=2.5,
        capacity_functional=2.5,
        capacity_technical=2.5,
        capacity_integration=2.5,
        geography="Spain",
        vertical="Manufacturing",
        arr_potential=100000,
        activation_velocity=5,
    )
    account = _make_account(erp_ecosystem="business_central", size=30)
    score, _ = compute_icp_score(partner, account)
    assert score <= 100.0


def test_tier_from_score():
    from app.models.partner import PartnerTier
    assert tier_from_score(90) == PartnerTier.platinum
    assert tier_from_score(85) == PartnerTier.platinum
    assert tier_from_score(84.9) == PartnerTier.gold
    assert tier_from_score(70) == PartnerTier.gold
    assert tier_from_score(69.9) == PartnerTier.silver
    assert tier_from_score(50) == PartnerTier.silver
    assert tier_from_score(49.9) == PartnerTier.bronze
    assert tier_from_score(0) == PartnerTier.bronze


@pytest.mark.asyncio
async def test_scoring_engine_fallback_to_defaults():
    """ScoringEngine returns DEFAULT_WEIGHTS when no active version in DB."""
    engine = ScoringEngine()

    # Mock DB that returns no active version
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    weights = await engine.load_active_weights(mock_db)
    assert weights == DEFAULT_WEIGHTS


@pytest.mark.asyncio
async def test_scoring_engine_loads_db_weights():
    """ScoringEngine loads weights from an active ScoringWeightVersion."""
    engine = ScoringEngine()

    custom_weights = {**DEFAULT_WEIGHTS, "erp_ecosystem_fit": 0.30, "arr_potential": 0.00}

    mock_version = MagicMock()
    mock_version.version = 2
    mock_version.id = uuid.uuid4()
    mock_version.weights = json.dumps(custom_weights)

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_version
    mock_db.execute = AsyncMock(return_value=mock_result)

    weights = await engine.load_active_weights(mock_db)
    assert weights["erp_ecosystem_fit"] == 0.30
    assert weights["arr_potential"] == 0.00


# ── Integration tests — Weight Versioning API ────────────────────────────────


VALID_WEIGHTS = {
    "erp_ecosystem_fit": 0.25,
    "partner_type_match": 0.15,
    "capacity_score": 0.15,
    "geography_match": 0.10,
    "vertical_fit": 0.10,
    "company_size": 0.05,
    "arr_potential": 0.10,
    "activation_velocity": 0.10,
}


@pytest.mark.asyncio
async def test_create_weight_version(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/api/v1/scoring/weights",
        json={"weights": VALID_WEIGHTS, "rationale": "Test v1"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 1
    assert data["is_active"] is False
    assert data["weights"]["erp_ecosystem_fit"] == 0.25


@pytest.mark.asyncio
async def test_create_weight_version_and_activate(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/api/v1/scoring/weights",
        json={"weights": VALID_WEIGHTS, "rationale": "Activate immediately", "activate": True},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_activate_weight_version(client: AsyncClient, auth_headers: dict) -> None:
    # Create two versions
    r1 = await client.post(
        "/api/v1/scoring/weights",
        json={"weights": VALID_WEIGHTS, "activate": True},
        headers=auth_headers,
    )
    r2 = await client.post(
        "/api/v1/scoring/weights",
        json={"weights": VALID_WEIGHTS},
        headers=auth_headers,
    )
    v2_id = r2.json()["id"]

    # Activate v2
    resp = await client.post(
        f"/api/v1/scoring/weights/{v2_id}/activate",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    # Active endpoint should return v2
    active_resp = await client.get("/api/v1/scoring/weights/active", headers=auth_headers)
    assert active_resp.status_code == 200
    assert active_resp.json()["id"] == v2_id


@pytest.mark.asyncio
async def test_list_weight_versions(client: AsyncClient, auth_headers: dict) -> None:
    for _ in range(3):
        await client.post(
            "/api/v1/scoring/weights",
            json={"weights": VALID_WEIGHTS},
            headers=auth_headers,
        )
    resp = await client.get("/api/v1/scoring/weights", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 3


@pytest.mark.asyncio
async def test_create_invalid_weights_missing_dimension(
    client: AsyncClient, auth_headers: dict
) -> None:
    bad_weights = {k: v for k, v in VALID_WEIGHTS.items() if k != "arr_potential"}
    resp = await client.post(
        "/api/v1/scoring/weights",
        json={"weights": bad_weights},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_invalid_weights_dont_sum_to_one(
    client: AsyncClient, auth_headers: dict
) -> None:
    bad_weights = {**VALID_WEIGHTS, "erp_ecosystem_fit": 0.99}  # sum >> 1
    resp = await client.post(
        "/api/v1/scoring/weights",
        json={"weights": bad_weights},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_active_weights_none(client: AsyncClient, auth_headers: dict) -> None:
    """Returns null when no active version exists."""
    resp = await client.get("/api/v1/scoring/weights/active", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_default_weights(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get("/api/v1/scoring/weights/defaults/current", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "erp_ecosystem_fit" in data
    assert abs(sum(data.values()) - 1.0) < 0.01


@pytest.mark.asyncio
async def test_scoring_uses_active_weights(
    client: AsyncClient, auth_headers: dict
) -> None:
    """
    Create an account + partner, verify default score.
    Then activate a custom weight version, recalculate, and verify the score changed.
    """
    # Create account with Sage 200 (high ERP fit)
    acc_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Weight Test Corp", "erp_ecosystem": "sage_200", "size": 30, "geography": "Spain"},
        headers=auth_headers,
    )
    account_id = acc_resp.json()["id"]

    # Create partner
    p_resp = await client.post(
        "/api/v1/partners",
        json={
            "account_id": account_id,
            "type": "VAR",
            "geography": "Spain",
            "vertical": "Manufacturing",
            "arr_potential": 30000,
            "activation_velocity": 25,
        },
        headers=auth_headers,
    )
    assert p_resp.status_code == 201
    default_score = p_resp.json()["icp_score"]
    partner_id = p_resp.json()["id"]

    # Create a weight version that puts 100% weight on ERP ecosystem
    full_erp_weights = {k: 0.0 for k in DEFAULT_WEIGHTS}
    full_erp_weights["erp_ecosystem_fit"] = 1.0

    await client.post(
        "/api/v1/scoring/weights",
        json={"weights": full_erp_weights, "activate": True, "rationale": "ERP only"},
        headers=auth_headers,
    )

    # Recalculate with new active weights
    recalc_resp = await client.post(
        f"/api/v1/partners/{partner_id}/score/recalculate",
        headers=auth_headers,
    )
    assert recalc_resp.status_code == 200
    new_score = recalc_resp.json()["total"]  # ScoreBreakdown returns 'total' not 'icp_score'

    # sage_200 raw = 9, weight = 1.0, total = 9 * 10 = 90
    assert new_score == pytest.approx(90.0, abs=0.1)
    assert new_score != default_score
