"""Generate the synthetic Contoso Logistics toll dataset (seeded, reproducible).

Writes:
  data/customers.csv, data/lanes.csv, data/shipments.csv, data/toll_rates.csv
  data/surcharge_proposals.csv  (default proposal: 100% recovery, % of freight)
  data/summary.json             (Python totals, used for the JS parity check)
  ../../site/demos/data/02-road-toll.js  (compact copy loaded by the demo page)

Usage: python src/generate_data.py
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

import toll

SEED = 2026


def r2(x: float) -> float:
    """Half-up rounding to cents, same as the JS port."""
    return toll.round_half_up(x, 2)

N_CUSTOMERS = 40
N_SHIPMENTS = 2000
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
DATA = PROJECT / "data"
SITE_DATA = PROJECT.parent.parent / "site" / "demos" / "data"

INDUSTRIES = ["Automotive OEM", "Steel manufacturer", "Retail chain", "Chemicals producer",
              "Food and beverage", "Building materials", "Consumer electronics", "Paper and packaging",
              "Agri-food", "Machinery maker"]
REGIONS = ["North", "East", "South", "West", "Central", "Delta"]


def generate(seed: int = SEED) -> tuple[list[dict], list[dict], list[dict]]:
    rng = random.Random(seed)

    lanes = []
    i = 0
    for origin in ("Port terminal", "Inland hub"):
        for region in REGIONS:
            for kind in ("DC", "Plant"):
                if len(lanes) >= 18:
                    break
                i += 1
                dist = rng.randint(55, 260)
                share = round(rng.uniform(0.35, 0.95), 2)
                lanes.append({
                    "lane_id": f"L{i:02d}",
                    "name": f"{origin} to {kind} {region}",
                    "distance_km": dist,
                    "tolled_share": share,
                    "tolled_km": round(dist * share, 1),
                })

    customers = []
    for c in range(1, N_CUSTOMERS + 1):
        customers.append({
            "customer_id": f"C{c:03d}",
            "name": f"Customer {c:03d}",
            "industry": rng.choice(INDUSTRIES),
            "allocation_basis": "pallet" if rng.random() < 0.7 else "weight",
            "cost_ratio": round(rng.uniform(0.84, 0.95), 3),
            "rate_per_km": round(rng.uniform(1.45, 1.95), 2),
        })

    # Zipf-like customer volumes: a few large accounts, a long tail.
    weights = [1.0 / (k ** 0.9) for k in range(1, N_CUSTOMERS + 1)]
    rng.shuffle(weights)
    co2_pop, co2_w = [1, 2, 3, 4, 5], [10, 20, 45, 15, 10]
    wc_pop, wc_w = toll.WEIGHT_CLASSES, [5, 10, 30, 55]

    shipments = []
    for n in range(1, N_SHIPMENTS + 1):
        cust = rng.choices(customers, weights=weights)[0]
        lane = rng.choice(lanes)
        pallets = min(33, max(1, int(rng.triangular(1, 33, 8))))
        weight_kg = min(toll.TRUCK_PAYLOAD_KG, round(pallets * rng.uniform(250, 700)))
        fill = pallets / toll.TRUCK_PALLET_PLACES
        revenue = round(lane["distance_km"] * cust["rate_per_km"] * (0.18 + 0.82 * fill) * rng.uniform(0.95, 1.08), 2)
        cost = round(revenue * cust["cost_ratio"] * rng.uniform(0.97, 1.03), 2)
        shipments.append({
            "shipment_id": f"S{n:05d}",
            "customer_id": cust["customer_id"],
            "lane_id": lane["lane_id"],
            "co2_class": rng.choices(co2_pop, weights=co2_w)[0],
            "weight_class": rng.choices(wc_pop, weights=wc_w)[0],
            "pallets": pallets,
            "weight_kg": weight_kg,
            "revenue_eur": revenue,
            "cost_eur": cost,
        })
    return customers, lanes, shipments


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    customers, lanes, shipments = generate()
    cust_map = {c["customer_id"]: c for c in customers}
    lane_map = {l["lane_id"]: l for l in lanes}
    impact = toll.customer_impact(shipments, cust_map, lane_map)

    DATA.mkdir(exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    _write_csv(DATA / "customers.csv", [{k: c[k] for k in ("customer_id", "name", "industry", "allocation_basis")} for c in customers])
    _write_csv(DATA / "lanes.csv", lanes)
    _write_csv(DATA / "shipments.csv", shipments)
    _write_csv(DATA / "toll_rates.csv", [
        {"co2_class": co2, "weight_class": w, "weight_class_label": toll.WEIGHT_CLASS_LABELS[w],
         "eur_per_km": r, "note": "ILLUSTRATIVE, not an official tariff"}
        for (co2, w), r in sorted(toll.RATES.items())
    ])

    proposals = []
    for cid in cust_map:
        p = toll.propose(impact[cid], "pct", 100)
        proposals.append({
            "customer_id": cid, "method": p.method, "recovery_pct": p.recovery_pct,
            "unit_rate": p.unit_rate, "toll_eur": round(p.toll_eur, 2), "surcharge_eur": r2(p.surcharge_eur),
            "increase_pct": round(p.increase_pct, 2), "margin_pct_before": round(p.margin_pct_before, 2),
            "margin_pct_after": round(p.margin_pct_after, 2), "tier": p.tier,
        })
    _write_csv(DATA / "surcharge_proposals.csv", proposals)

    tiers = {}
    for p in proposals:
        tiers[p["tier"]] = tiers.get(p["tier"], 0) + 1
    summary = {
        "seed": SEED,
        "shipments": len(shipments),
        "customers": len(customers),
        "lanes": len(lanes),
        "total_toll_eur": r2(sum(v["toll"] for v in impact.values())),
        "total_revenue_eur": r2(sum(v["revenue"] for v in impact.values())),
        "total_cost_eur": round(sum(v["cost"] for v in impact.values()), 2),
        "default_surcharge_eur": r2(sum(p["surcharge_eur"] for p in proposals)),
        "tiers_default_proposal": tiers,
        "toll_by_customer": {cid: r2(v["toll"]) for cid, v in impact.items()},
    }
    (DATA / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    compact = {
        "note": "Synthetic Contoso Logistics data. Toll rates are ILLUSTRATIVE, not official tariffs.",
        "truck": {"pallets": toll.TRUCK_PALLET_PLACES, "payloadKg": toll.TRUCK_PAYLOAD_KG},
        "rates": {f"{co2}|{w}": r for (co2, w), r in toll.RATES.items()},
        "customers": [[c["customer_id"], c["name"], c["industry"], c["allocation_basis"]] for c in customers],
        "lanes": [[l["lane_id"], l["name"], l["distance_km"], l["tolled_km"]] for l in lanes],
        "shipmentCols": ["customer_id", "lane_id", "co2_class", "weight_class", "pallets", "weight_kg", "revenue_eur", "cost_eur"],
        "shipments": [[s["customer_id"], s["lane_id"], s["co2_class"], s["weight_class"], s["pallets"],
                       s["weight_kg"], s["revenue_eur"], s["cost_eur"]] for s in shipments],
        "pythonSummary": {k: summary[k] for k in ("total_toll_eur", "total_revenue_eur", "default_surcharge_eur")},
    }
    (SITE_DATA / "02-road-toll.js").write_text(
        "/* Generated by projects/02-road-toll-surcharge-app/src/generate_data.py. Do not edit. */\n"
        "window.TOLL_DATA = " + json.dumps(compact, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "toll_by_customer"}, indent=2))


if __name__ == "__main__":
    main()
