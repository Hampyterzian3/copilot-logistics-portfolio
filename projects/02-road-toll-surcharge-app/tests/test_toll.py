import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "src"))

import generate_data  # noqa: E402
import toll  # noqa: E402

REPO = PROJECT.parent.parent


def test_rate_table_complete_and_monotonic():
    assert len(toll.RATES) == 5 * 4
    for w in toll.WEIGHT_CLASSES:
        by_co2 = [toll.rate(c, w) for c in (1, 2, 3, 4, 5)]
        assert by_co2 == sorted(by_co2, reverse=True), "cleaner trucks must not pay more"
    for c in (1, 2, 3, 4, 5):
        by_w = [toll.rate(c, w) for w in toll.WEIGHT_CLASSES]
        assert by_w == sorted(by_w), "heavier trucks must not pay less"


def test_unknown_rate_raises():
    with pytest.raises(ValueError):
        toll.rate(6, "W4")


def test_allocation_share_pallet_and_weight():
    assert toll.allocation_share(33, 0, "pallet") == 1.0
    assert toll.allocation_share(11, 0, "pallet") == pytest.approx(1 / 3)
    assert toll.allocation_share(0, 12000, "weight") == 0.5
    assert toll.allocation_share(50, 0, "pallet") == 1.0  # capped
    with pytest.raises(ValueError):
        toll.allocation_share(1, 1, "volume")


def test_shipment_toll_formula():
    # 100 tolled km x W4 class-1 rate x full truck
    assert toll.shipment_toll(100, 1, "W4", 33, 0, "pallet") == pytest.approx(100 * toll.rate(1, "W4"))
    # half the truck pays half
    full = toll.shipment_toll(80, 3, "W3", 0, 24000, "weight")
    half = toll.shipment_toll(80, 3, "W3", 0, 12000, "weight")
    assert half == pytest.approx(full / 2)


def test_round_half_up_matches_js_semantics():
    assert toll.round_half_up(2.5) == 3
    assert toll.round_half_up(0.125, 2) == 0.13
    assert toll.round_half_up(-0.5) == 0


def _impact():
    impact = {"customer_id": "C1", "shipments": 10, "revenue": 10000.0, "cost": 9000.0,
              "toll": 400.0, "km": 2000.0, "tolled_km": 1500.0}
    return impact


@pytest.mark.parametrize("method", toll.METHODS)
def test_full_recovery_restores_margin_within_rounding(method):
    p = toll.propose(_impact(), method, 100)
    assert p.surcharge_eur == pytest.approx(400.0, abs=1.0)
    assert p.margin_after == pytest.approx(p.margin_before_toll, abs=1.0)
    assert p.margin_after_toll == pytest.approx(600.0)


def test_unit_rates():
    imp = _impact()
    assert toll.propose(imp, "flat", 100).unit_rate == 40.0
    assert toll.propose(imp, "pct", 100).unit_rate == 4.0
    assert toll.propose(imp, "km", 50).unit_rate == 0.1


def test_zero_recovery_is_auto_and_absorbs_toll():
    p = toll.propose(_impact(), "pct", 0)
    assert p.surcharge_eur == 0
    assert p.tier == "Auto-approved"
    assert p.margin_after == pytest.approx(600.0)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        toll.propose(_impact(), "weekly", 100)
    with pytest.raises(ValueError):
        toll.propose(_impact(), "pct", 200)


@pytest.mark.parametrize("inc,eur,tier", [
    (1.0, 50, "Auto-approved"),
    (3.5, 200, "Auto-approved"),
    (3.6, 100, "Commercial manager"),
    (2.0, 300, "Commercial manager"),
    (5.1, 100, "Steering committee"),
    (2.0, 900, "Steering committee"),
])
def test_approval_tiers(inc, eur, tier):
    assert toll.approval_tier(inc, eur) == tier


def test_generator_is_reproducible_and_sized():
    a = generate_data.generate(7)
    b = generate_data.generate(7)
    assert a == b
    customers, lanes, shipments = generate_data.generate()
    assert len(customers) == 40 and len(shipments) == 2000 and len(lanes) == 18
    assert all(0 < l["tolled_km"] <= l["distance_km"] for l in lanes)
    assert len({s["customer_id"] for s in shipments}) == 40


def test_summary_matches_fresh_computation():
    customers, lanes, shipments = generate_data.generate()
    impact = toll.customer_impact(shipments, {c["customer_id"]: c for c in customers},
                                  {l["lane_id"]: l for l in lanes})
    total = sum(v["toll"] for v in impact.values())
    summary = json.loads((PROJECT / "data" / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_toll_eur"] == toll.round_half_up(sum(v["toll"] for v in impact.values()), 2)
    assert math.isclose(sum(summary["toll_by_customer"].values()), total, abs_tol=0.5)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_port_matches_python_totals():
    """Runs the calculation block embedded in the demo page under Node and compares totals."""
    script = PROJECT / "src" / "check_js_parity.js"
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    summary = json.loads((PROJECT / "data" / "summary.json").read_text(encoding="utf-8"))
    assert js["total_toll_eur"] == summary["total_toll_eur"]
    assert js["total_revenue_eur"] == summary["total_revenue_eur"]
    assert js["default_surcharge_eur"] == summary["default_surcharge_eur"]
    assert js["tiers_default_proposal"] == summary["tiers_default_proposal"]
    assert js["toll_by_customer"] == summary["toll_by_customer"]
