"""Seeded synthetic data for the Inbound Risk Early-Warning Agent (Contoso Logistics).

Everything here is invented. Carrier and customer names are Microsoft sample
company names; postcode areas use made-up zone codes (for example FR-Z07).

Two kinds of records are produced:
- history: 12 months of closed shipments, each with a mid-transit snapshot of
  the same features the live model sees, plus the real outcome (late, lost).
- in_transit: about 300 open shipments as of AS_OF, with scan events.

Outcomes in history come from a hidden "true" process that is deliberately
different from the scoring weights, so the backtest is a fair test.
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta

SEED = 404
AS_OF = datetime(2026, 11, 9, 8, 0)          # Monday 08:00
HISTORY_START = datetime(2025, 11, 1)
HISTORY_END = datetime(2026, 11, 1)
N_HISTORY = 7200
N_IN_TRANSIT = 300

# code, hub, country, customs required, base transit days to NL
ORIGINS = [
    ("PL-POZ", "Poznan hub", "PL", False, 2.0),
    ("CZ-BRQ", "Brno hub", "CZ", False, 1.8),
    ("IT-MIL", "Milan hub", "IT", False, 2.3),
    ("ES-ZAZ", "Zaragoza hub", "ES", False, 2.8),
    ("GB-MID", "Midlands hub", "GB", True, 2.4),
    ("TR-BUR", "Bursa hub", "TR", True, 4.2),
]
DEST_OFFSET = {"NL": 0.0, "BE": 0.2, "DE": -0.2, "FR": 0.4}
CROSS_DOCK = {"NL": "Venlo cross-dock", "BE": "Liege cross-dock",
              "DE": "Duisburg cross-dock", "FR": "Lille cross-dock"}

# name, true on-time propensity (hidden)
CARRIERS = [
    ("Fabrikam Freight", 0.95), ("Northwind Express", 0.93), ("Litware Logistics", 0.90),
    ("Proseware Parcel", 0.87), ("Woodgrove Road", 0.84), ("Tailspin Haulage", 0.80),
]

CUSTOMERS = [
    "Adventure Works", "Wide World Importers", "Tailwind Traders", "Coho Winery",
    "Lamna Healthcare", "Trey Research", "Relecloud", "VanArsdel",
]

AREA_COUNT = {"NL": 5, "BE": 4, "DE": 5, "FR": 7}
HIGH_RISK_AREAS = {"FR-Z07": 0.030, "BE-Z03": 0.024}   # seeded true loss rates

MILESTONES = [
    # code, label, progress share of transit, normal dwell hours after this scan
    ("PICKED_UP", "pickup", 0.05, 10.0),
    ("DEPARTED_ORIGIN_HUB", "hub departure", 0.15, 28.0),
    ("ARRIVED_CROSS_DOCK", "cross-dock arrival", 0.55, 12.0),
    ("CUSTOMS_LODGED", "customs lodgement", 0.60, 16.0),
    ("DEPARTED_CROSS_DOCK", "cross-dock departure", 0.65, 20.0),
    ("ARRIVED_DEST_DEPOT", "depot arrival", 0.85, 14.0),
    ("OUT_FOR_DELIVERY", "out-for-delivery", 0.97, 8.0),
]

ALL = ("NL", "BE", "DE", "FR")
HOLIDAYS = {
    date(2025, 11, 1): ("All Saints' Day", ("BE", "FR")),
    date(2025, 11, 11): ("Armistice Day", ("BE", "FR")),
    date(2025, 12, 25): ("Christmas Day", ALL),
    date(2025, 12, 26): ("Second Christmas Day", ("NL", "DE")),
    date(2026, 1, 1): ("New Year's Day", ALL),
    date(2026, 4, 6): ("Easter Monday", ALL),
    date(2026, 4, 27): ("King's Day", ("NL",)),
    date(2026, 5, 1): ("Labour Day", ("BE", "DE", "FR")),
    date(2026, 5, 14): ("Ascension Day", ALL),
    date(2026, 5, 25): ("Whit Monday", ALL),
    date(2026, 7, 14): ("Bastille Day", ("FR",)),
    date(2026, 7, 21): ("Belgian National Day", ("BE",)),
    date(2026, 10, 3): ("German Unity Day", ("DE",)),
    date(2026, 11, 11): ("Armistice Day", ("BE", "FR")),
}


def build_areas(rng: random.Random) -> list[dict]:
    areas = []
    for cc, n in AREA_COUNT.items():
        for i in range(1, n + 1):
            code = f"{cc}-Z{i:02d}"
            true_loss = HIGH_RISK_AREAS.get(code, round(rng.uniform(0.0015, 0.0045), 4))
            areas.append({"area": code, "country": cc, "true_loss_rate": true_loss,
                          "high_risk_seeded": code in HIGH_RISK_AREAS})
    return areas


def build_lanes(rng: random.Random) -> list[dict]:
    lanes = []
    for code, hub, origin_cc, customs, base in ORIGINS:
        for dest, off in DEST_OFFSET.items():
            true_delay = rng.uniform(0.05, 0.16)
            if (code, dest) in {("TR-BUR", "FR"), ("ES-ZAZ", "DE"), ("GB-MID", "BE")}:
                true_delay += 0.12
            lanes.append({"lane": f"{code} > {dest}", "origin": code, "origin_hub": hub,
                          "origin_country": origin_cc, "dest_country": dest,
                          "customs_required": customs, "base_transit_days": round(base + off, 2),
                          "true_delay_rate": round(true_delay, 4)})
    return lanes


def non_working(start: datetime, end: datetime, country: str) -> tuple[int, str]:
    """Weekend and public-holiday days after start.date() up to and including end.date()."""
    n, name = 0, ""
    d = start.date() + timedelta(days=1)
    while d <= end.date():
        hol = HOLIDAYS.get(d)
        if hol and country in hol[1]:
            n += 1
            name = name or hol[0]
        elif d.weekday() >= 5:
            n += 1
        d += timedelta(days=1)
    return n, name


def snapshot(rng: random.Random, lane: dict, carrier: tuple, area: dict, snap_time: datetime) -> dict:
    """Mid-transit state of one shipment at snap_time."""
    steps = [m for m in MILESTONES if lane["customs_required"] or m[0] != "CUSTOMS_LODGED"]
    idx = rng.randrange(len(steps))
    code, label, progress, norm = steps[idx]
    base = lane["base_transit_days"]
    carrier_true = carrier[1]

    p_stuck = 0.05 + (0.95 - carrier_true) * 0.9 + (0.10 if area["high_risk_seeded"] else 0.0)
    if rng.random() < p_stuck:
        dwell = norm * rng.uniform(1.6, 4.5)
    else:
        dwell = norm * min(1.4, rng.lognormvariate(math.log(0.6), 0.45))
    dwell = round(dwell, 1)

    if not lane["customs_required"]:
        customs = "not_required"
    else:
        c_idx = [s[0] for s in steps].index("CUSTOMS_LODGED")
        if idx < c_idx:
            customs = "pending"
        elif idx == c_idx:
            customs = "held" if rng.random() < 0.25 else "pending"
        else:
            customs = "cleared"

    lead = base + rng.uniform(0.3, 1.6)
    elapsed = base * progress * rng.uniform(0.85, 1.3) + max(0.0, dwell - norm) / 24.0
    ship_time = snap_time - timedelta(days=elapsed)
    promised = ship_time + timedelta(days=lead)
    days_to_promise = round((promised - snap_time).total_seconds() / 86400.0, 2)
    remaining = round(base * (1.0 - progress), 2)
    nw, hol = non_working(snap_time, promised, lane["dest_country"])
    location = {
        "PICKED_UP": lane["origin_hub"], "DEPARTED_ORIGIN_HUB": lane["origin_hub"],
        "ARRIVED_CROSS_DOCK": CROSS_DOCK[lane["dest_country"]],
        "CUSTOMS_LODGED": CROSS_DOCK[lane["dest_country"]],
        "DEPARTED_CROSS_DOCK": CROSS_DOCK[lane["dest_country"]],
        "ARRIVED_DEST_DEPOT": f"{area['area']} depot", "OUT_FOR_DELIVERY": f"{area['area']} depot",
    }[code]
    return {
        "lane": lane["lane"], "origin": lane["origin"], "dest_country": lane["dest_country"],
        "carrier": carrier[0], "area": area["area"],
        "ship_time": ship_time, "snapshot_time": snap_time, "promised_time": promised,
        "milestone_index": idx, "milestones": steps,
        "last_scan": code, "last_scan_label": label, "last_scan_location": location,
        "dwell_hours": dwell, "dwell_norm_hours": norm, "customs_status": customs,
        "days_to_promise": days_to_promise, "remaining_transit_days": remaining,
        "non_working_days": nw, "holiday_name": hol,
    }


def true_outcome(rng: random.Random, s: dict, lane: dict, carrier: tuple, area: dict) -> tuple[bool, bool]:
    """Hidden ground truth. Not the scoring model."""
    ratio = s["dwell_hours"] / s["dwell_norm_hours"]
    slack = s["days_to_promise"] - s["remaining_transit_days"]
    z = (-4.3
         + 8.0 * (lane["true_delay_rate"] - 0.12)
         + 12.0 * (0.92 - carrier[1])
         + 1.5 * min(max(ratio - 1.3, 0.0), 3.0)
         + (2.4 if s["customs_status"] == "held" else 0.5 if s["customs_status"] == "pending" else 0.0)
         + 2.2 * min(max(0.6 - slack, 0.0), 2.5)
         + 0.3 * s["non_working_days"])
    late = rng.random() < 1.0 / (1.0 + math.exp(-z))
    lost = rng.random() < area["true_loss_rate"] * (1.0 + 1.5 * max(ratio - 1.5, 0.0))
    return late or lost, lost


def pick(rng, lanes, areas, customer_lanes):
    customer = rng.choice(CUSTOMERS)
    lane = rng.choice(customer_lanes[customer])
    area = rng.choice([a for a in areas if a["country"] == lane["dest_country"]])
    carrier = rng.choices(CARRIERS, weights=[22, 20, 18, 16, 13, 11])[0]
    return customer, lane, area, carrier


def generate(seed: int = SEED) -> dict:
    rng = random.Random(seed)
    areas = build_areas(rng)
    lanes = build_lanes(rng)
    customer_lanes = {c: rng.sample(lanes, 7) for c in CUSTOMERS}

    history = []
    span = (HISTORY_END - HISTORY_START).total_seconds()
    for i in range(N_HISTORY):
        customer, lane, area, carrier = pick(rng, lanes, areas, customer_lanes)
        snap_time = HISTORY_START + timedelta(seconds=rng.uniform(0, span))
        s = snapshot(rng, lane, carrier, area, snap_time)
        late, lost = true_outcome(rng, s, lane, carrier, area)
        s.update({"shipment_id": f"H{100000 + i}", "customer": customer, "late": late, "lost": lost})
        history.append(s)
    history.sort(key=lambda r: r["snapshot_time"])

    in_transit, events = [], []
    for i in range(N_IN_TRANSIT):
        customer, lane, area, carrier = pick(rng, lanes, areas, customer_lanes)
        s = snapshot(rng, lane, carrier, area, AS_OF)
        sid = f"CTL-{260000 + i * 7 + rng.randrange(7)}"
        s.update({"shipment_id": sid, "customer": customer,
                  "po_ref": f"PO-{rng.randrange(40000, 99999)}",
                  "pieces": rng.randrange(1, 34)})
        in_transit.append(s)
        # scan events: last scan is dwell_hours before AS_OF, earlier scans step back by norm dwell
        t = AS_OF - timedelta(hours=s["dwell_hours"])
        chain = []
        for j in range(s["milestone_index"], -1, -1):
            code, label, _, norm = s["milestones"][j]
            loc = s["last_scan_location"] if j == s["milestone_index"] else None
            chain.append((code, label, t, loc))
            if j > 0:
                prev_norm = s["milestones"][j - 1][3]
                t = t - timedelta(hours=prev_norm * rng.uniform(0.5, 1.0))
        for code, label, ts, loc in reversed(chain):
            if loc is None:
                loc = {"PICKED_UP": lane["origin_hub"], "DEPARTED_ORIGIN_HUB": lane["origin_hub"],
                       "ARRIVED_DEST_DEPOT": f"{area['area']} depot"}.get(code, CROSS_DOCK[lane["dest_country"]])
            events.append({"shipment_id": sid, "event": code, "description": label,
                           "location": loc, "timestamp": ts.strftime("%Y-%m-%dT%H:%M")})

    return {"areas": areas, "lanes": lanes, "carriers": CARRIERS, "customers": CUSTOMERS,
            "history": history, "in_transit": in_transit, "scan_events": events}
