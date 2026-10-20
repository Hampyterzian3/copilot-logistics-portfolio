"""Road-toll surcharge model for Contoso Logistics (synthetic portfolio project).

Toll per shipment = tolled km on the lane x rate (EUR/km) by CO2 emission class
and weight class of the truck, allocated to the shipment by its share of the
truck (pallet places or weight, per the customer's contract basis).

ILLUSTRATIVE RATES ONLY. The rate table below is invented for this demo and is
NOT an official tariff of any government or toll operator.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

TRUCK_PALLET_PLACES = 33
TRUCK_PAYLOAD_KG = 24000

# Weight classes of the vehicle (technically permissible maximum mass).
WEIGHT_CLASSES = ["W1", "W2", "W3", "W4"]
WEIGHT_CLASS_LABELS = {"W1": "3.5-12 t", "W2": "12-18 t", "W3": "18-32 t", "W4": "over 32 t"}

# ILLUSTRATIVE base rate in EUR per tolled km for CO2 emission class 1 (highest emitting).
_BASE_EUR_PER_KM = {"W1": 0.110, "W2": 0.145, "W3": 0.185, "W4": 0.225}
# ILLUSTRATIVE discount factor by CO2 emission class (1 = highest emitting, 5 = zero emission).
_CO2_FACTOR = {1: 1.00, 2: 0.95, 3: 0.88, 4: 0.50, 5: 0.25}


def round_half_up(x: float, nd: int = 0) -> float:
    """Round half up, identical to the JS port (Math.floor(x * 10**nd + 0.5) / 10**nd)."""
    f = 10 ** nd
    return math.floor(x * f + 0.5) / f


def build_rate_table() -> dict[tuple[int, str], float]:
    """ILLUSTRATIVE EUR/km rate per (co2_class, weight_class)."""
    return {
        (co2, w): round_half_up(_BASE_EUR_PER_KM[w] * _CO2_FACTOR[co2], 3)
        for co2 in _CO2_FACTOR
        for w in WEIGHT_CLASSES
    }


RATES = build_rate_table()


def rate(co2_class: int, weight_class: str) -> float:
    if (co2_class, weight_class) not in RATES:
        raise ValueError(f"No rate for CO2 class {co2_class}, weight class {weight_class}")
    return RATES[(co2_class, weight_class)]


def allocation_share(pallets: float, weight_kg: float, basis: str) -> float:
    """Share of the truck used by a shipment, capped at 1."""
    if basis == "pallet":
        share = pallets / TRUCK_PALLET_PLACES
    elif basis == "weight":
        share = weight_kg / TRUCK_PAYLOAD_KG
    else:
        raise ValueError(f"Unknown allocation basis: {basis}")
    return min(max(share, 0.0), 1.0)


def shipment_toll(tolled_km: float, co2_class: int, weight_class: str,
                  pallets: float, weight_kg: float, basis: str) -> float:
    """Toll (EUR) allocated to one shipment. Unrounded; round totals for display."""
    return tolled_km * rate(co2_class, weight_class) * allocation_share(pallets, weight_kg, basis)


def customer_impact(shipments: list[dict], customers: dict[str, dict], lanes: dict[str, dict]) -> dict[str, dict]:
    """Aggregate toll, revenue, cost and km per customer.

    shipments: dicts with customer_id, lane_id, co2_class, weight_class, pallets, weight_kg, revenue_eur, cost_eur
    customers: customer_id -> dict with allocation_basis
    lanes: lane_id -> dict with distance_km, tolled_km
    """
    out: dict[str, dict] = {
        cid: {"customer_id": cid, "shipments": 0, "revenue": 0.0, "cost": 0.0,
              "toll": 0.0, "km": 0.0, "tolled_km": 0.0}
        for cid in customers
    }
    for s in shipments:
        c = out[s["customer_id"]]
        lane = lanes[s["lane_id"]]
        c["shipments"] += 1
        c["revenue"] += s["revenue_eur"]
        c["cost"] += s["cost_eur"]
        c["km"] += lane["distance_km"]
        c["tolled_km"] += lane["tolled_km"]
        c["toll"] += shipment_toll(lane["tolled_km"], s["co2_class"], s["weight_class"],
                                   s["pallets"], s["weight_kg"], customers[s["customer_id"]]["allocation_basis"])
    return out


# Approval tiers. Price increase is surcharge as % of current freight revenue.
AUTO_MAX_INCREASE_PCT = 3.5
AUTO_MAX_EUR = 200.0
CM_MAX_INCREASE_PCT = 5.0
CM_MAX_EUR = 500.0

METHODS = ("flat", "pct", "km")


def approval_tier(increase_pct: float, surcharge_eur: float) -> str:
    if increase_pct <= AUTO_MAX_INCREASE_PCT and surcharge_eur <= AUTO_MAX_EUR:
        return "Auto-approved"
    if increase_pct <= CM_MAX_INCREASE_PCT and surcharge_eur <= CM_MAX_EUR:
        return "Commercial manager"
    return "Steering committee"


@dataclass
class Proposal:
    customer_id: str
    method: str
    recovery_pct: float
    unit_rate: float          # EUR per shipment | % of freight | EUR per km
    surcharge_eur: float      # surcharge billed on the period's volumes
    toll_eur: float
    margin_before_toll: float
    margin_after_toll: float  # toll absorbed, no surcharge
    margin_after: float       # toll paid, surcharge billed
    margin_pct_before: float
    margin_pct_after: float
    increase_pct: float
    tier: str


def propose(impact: dict, method: str, recovery_pct: float) -> Proposal:
    """Surcharge proposal for one customer. Unit rates are rounded as they would be on a tariff sheet."""
    if method not in METHODS:
        raise ValueError(f"Unknown method: {method}")
    if not 0 <= recovery_pct <= 150:
        raise ValueError("recovery_pct must be between 0 and 150")
    target = impact["toll"] * recovery_pct / 100.0
    rev = impact["revenue"]
    if method == "flat":
        unit = round_half_up(target / impact["shipments"], 2) if impact["shipments"] else 0.0
        surcharge = unit * impact["shipments"]
    elif method == "pct":
        unit = round_half_up(target / rev * 100.0, 2) if rev else 0.0
        surcharge = rev * unit / 100.0
    else:
        unit = round_half_up(target / impact["km"], 3) if impact["km"] else 0.0
        surcharge = unit * impact["km"]
    margin0 = rev - impact["cost"]
    margin1 = margin0 - impact["toll"]
    margin2 = margin1 + surcharge
    increase = surcharge / rev * 100.0 if rev else 0.0
    return Proposal(
        customer_id=impact["customer_id"], method=method, recovery_pct=recovery_pct,
        unit_rate=unit, surcharge_eur=surcharge, toll_eur=impact["toll"],
        margin_before_toll=margin0, margin_after_toll=margin1, margin_after=margin2,
        margin_pct_before=margin0 / rev * 100.0 if rev else 0.0,
        margin_pct_after=margin2 / (rev + surcharge) * 100.0 if rev + surcharge else 0.0,
        increase_pct=increase, tier=approval_tier(increase, surcharge),
    )
