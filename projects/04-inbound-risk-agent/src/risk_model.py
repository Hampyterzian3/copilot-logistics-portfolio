"""Transparent inbound risk score (0-100) for in-transit shipments.

Seven factors, each mapped to a 0-1 sub-score by a straight line between a
"no concern" and a "full concern" point, then multiplied by a fixed weight.
Weights add up to 100, so the score reads as points out of 100 and every
point can be traced to a reason a planner can check.

The same logic is ported to site/demos/js/04-risk-model.js. Keep both in step:
tests/test_js_parity.py fails if any score, band or reason text differs.
"""
from __future__ import annotations

import math
from collections import defaultdict

# factor, weight (sum 100)
WEIGHTS = (
    ("lane", 15),      # lane historical delay rate
    ("area", 15),      # destination postcode-area loss rate
    ("carrier", 15),   # carrier on-time rate
    ("dwell", 20),     # hours since last scan vs normal dwell for that scan
    ("customs", 10),   # customs status
    ("slack", 20),     # days to promised delivery minus transit still to run
    ("calendar", 5),   # weekend or public holiday before promised date
)
# band, minimum score (checked top down); below the last one is "on_track"
BANDS = (("critical", 55), ("at_risk", 40), ("watch", 25))
BAND_LABELS = {"critical": "Critical", "at_risk": "At risk", "watch": "Watch", "on_track": "On track"}
MIN_REASON_POINTS = 3.0
MAX_REASONS = 3

FEATURE_KEYS = (
    "shipment_id", "customer", "carrier", "lane", "area", "dest_country",
    "last_scan_label", "last_scan_location", "lane_delay_rate", "area_loss_rate",
    "network_loss_rate", "carrier_on_time", "dwell_hours", "dwell_norm_hours",
    "customs_status", "days_to_promise", "remaining_transit_days",
    "non_working_days", "holiday_name",
)


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def ri(x: float) -> int:
    """Round half up to an integer (same as Math.floor(x + 0.5) in JS)."""
    return math.floor(x + 0.5)


def r1(x: float) -> float:
    return math.floor(x * 10.0 + 0.5) / 10.0


def f1(x: float) -> str:
    return f"{r1(x):.1f}"


def pct0(x: float) -> str:
    return f"{ri(x * 100.0)}%"


def subscores(f: dict) -> dict:
    ratio = f["dwell_hours"] / f["dwell_norm_hours"]
    slack = f["days_to_promise"] - f["remaining_transit_days"]
    if f["holiday_name"]:
        cal = 1.0
    elif f["non_working_days"] > 0:
        cal = 0.6
    else:
        cal = 0.0
    return {
        "lane": clamp01((f["lane_delay_rate"] - 0.06) / 0.24),
        "area": clamp01((f["area_loss_rate"] - 0.004) / 0.016),
        "carrier": clamp01((0.95 - f["carrier_on_time"]) / 0.20),
        "dwell": clamp01((ratio - 1.0) / 2.0),
        "customs": 1.0 if f["customs_status"] == "held" else 0.5 if f["customs_status"] == "pending" else 0.0,
        "slack": clamp01((1.0 - slack) / 2.0),
        "calendar": cal,
    }


def reason_text(factor: str, f: dict) -> str:
    if factor == "lane":
        return f"Lane {f['lane']} ran late on {pct0(f['lane_delay_rate'])} of shipments in the last 12 months"
    if factor == "area":
        return (f"Destination area {f['area']} lost {f1(f['area_loss_rate'] * 100.0)}% of shipments, "
                f"against {f1(f['network_loss_rate'] * 100.0)}% across the network")
    if factor == "carrier":
        return f"{f['carrier']} delivered on time on {pct0(f['carrier_on_time'])} of shipments in the last 12 months"
    if factor == "dwell":
        ratio = f["dwell_hours"] / f["dwell_norm_hours"]
        return (f"No scan for {ri(f['dwell_hours'])} h since the {f['last_scan_label']} scan at {f['last_scan_location']}, "
                f"{f1(ratio)}x the usual {ri(f['dwell_norm_hours'])} h")
    if factor == "customs":
        return "Held by customs, not yet released" if f["customs_status"] == "held" else "Customs clearance still pending"
    if factor == "slack":
        if f["days_to_promise"] < 0:
            return (f"Already {f1(-f['days_to_promise'])} days past the promised date, "
                    f"about {f1(f['remaining_transit_days'])} days of transit left")
        return (f"Due in {f1(f['days_to_promise'])} days with about "
                f"{f1(f['remaining_transit_days'])} days of transit left")
    n = f["non_working_days"]
    unit = "day" if n == 1 else "days"
    if f["holiday_name"]:
        return f"{n} non-working {unit} before the promised date, including {f['holiday_name']}"
    return f"{n} weekend {unit} before the promised date"


def band_for(score: int) -> str:
    for band, minimum in BANDS:
        if score >= minimum:
            return band
    return "on_track"


def score_shipment(f: dict) -> dict:
    """Score one feature record. Returns score, band, points per factor and top reasons."""
    sub = subscores(f)
    total = 0.0
    pts = []
    for order, (factor, weight) in enumerate(WEIGHTS):
        p = weight * sub[factor]
        total += p
        pts.append((p, order, factor))
    score = min(100, ri(total))
    ranked = sorted(pts, key=lambda t: (-t[0], t[1]))
    reasons = [{"factor": fac, "points": r1(p), "text": reason_text(fac, f)}
               for p, _, fac in ranked if p >= MIN_REASON_POINTS][:MAX_REASONS]
    return {"score": score, "band": band_for(score),
            "points": {fac: r1(p) for p, _, fac in pts}, "reasons": reasons}


# ---------- reference rates from closed history ----------

def compute_rates(history: list[dict]) -> dict:
    """Lane delay rate, area loss rate and carrier on-time rate from closed shipments."""
    lane, area, carrier = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    lost_total = 0
    for h in history:
        lane[h["lane"]][0] += h["late"]; lane[h["lane"]][1] += 1
        area[h["area"]][0] += h["lost"]; area[h["area"]][1] += 1
        carrier[h["carrier"]][0] += (not h["late"]); carrier[h["carrier"]][1] += 1
        lost_total += h["lost"]
    return {
        "lane_delay_rate": {k: round(v[0] / v[1], 4) for k, v in lane.items()},
        "area_loss_rate": {k: round(v[0] / v[1], 4) for k, v in area.items()},
        "area_volume": {k: v[1] for k, v in area.items()},
        "carrier_on_time": {k: round(v[0] / v[1], 4) for k, v in carrier.items()},
        "network_loss_rate": round(lost_total / len(history), 4),
    }


def build_features(s: dict, rates: dict) -> dict:
    """Feature record for one shipment snapshot, using rates from history."""
    return {
        "shipment_id": s["shipment_id"], "customer": s["customer"], "carrier": s["carrier"],
        "lane": s["lane"], "area": s["area"], "dest_country": s["dest_country"],
        "last_scan_label": s["last_scan_label"], "last_scan_location": s["last_scan_location"],
        "lane_delay_rate": rates["lane_delay_rate"].get(s["lane"], 0.0),
        "area_loss_rate": rates["area_loss_rate"].get(s["area"], 0.0),
        "network_loss_rate": rates["network_loss_rate"],
        "carrier_on_time": rates["carrier_on_time"].get(s["carrier"], 0.95),
        "dwell_hours": s["dwell_hours"], "dwell_norm_hours": s["dwell_norm_hours"],
        "customs_status": s["customs_status"], "days_to_promise": s["days_to_promise"],
        "remaining_transit_days": s["remaining_transit_days"],
        "non_working_days": s["non_working_days"], "holiday_name": s["holiday_name"],
    }


# ---------- backtest ----------

def confusion(flags: list[bool], actual: list[bool]) -> dict:
    tp = sum(1 for f, a in zip(flags, actual) if f and a)
    fp = sum(1 for f, a in zip(flags, actual) if f and not a)
    fn = sum(1 for f, a in zip(flags, actual) if not f and a)
    tn = len(flags) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"flagged": tp + fp, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 4), "recall": round(recall, 4)}


def backtest(history: list[dict], cutoff) -> dict:
    """Rates from snapshots before cutoff; score and compare outcomes from cutoff onward."""
    train = [h for h in history if h["snapshot_time"] < cutoff]
    test = [h for h in history if h["snapshot_time"] >= cutoff]
    rates = compute_rates(train)
    scored = [score_shipment(build_features(h, rates)) for h in test]
    actual = [bool(h["late"]) for h in test]
    critical = confusion([s["band"] == "critical" for s in scored], actual)
    at_risk_plus = confusion([s["band"] in ("critical", "at_risk") for s in scored], actual)
    watch_plus = confusion([s["band"] != "on_track" for s in scored], actual)
    by_band = {}
    for band in ("critical", "at_risk", "watch", "on_track"):
        rows = [a for s, a in zip(scored, actual) if s["band"] == band]
        by_band[band] = {"shipments": len(rows), "late": sum(rows),
                         "late_rate": round(sum(rows) / len(rows), 4) if rows else 0.0}
    return {
        "train_snapshots": len(train), "test_snapshots": len(test),
        "cutoff": cutoff.strftime("%Y-%m-%d"),
        "test_late": sum(actual), "test_late_rate": round(sum(actual) / len(actual), 4),
        "critical": critical, "at_risk_or_above": at_risk_plus, "watch_or_above": watch_plus,
        "by_band": by_band,
    }
