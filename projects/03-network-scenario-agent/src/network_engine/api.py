"""Request/response contract behind POST /scenarios (see openapi.yaml).
Kept free of Azure imports so it can be unit tested locally."""
from __future__ import annotations

from .data import generate
from .model import MODES, run_scenario, summary

LIMITS = {
    "fuel_index": (0.5, 2.0),
    "co2_price_t": (0.0, 300.0),
    "handling_ldm": (0.0, 30.0),
    "max_stops": (1, 8),
}
LABELS = {"direct": "Direct full-load", "milkrun": "Regional milk-run",
          "crossdock": "Cross-dock consolidation", "bestmix": "Best mix"}


class ValidationError(ValueError):
    pass


def parse_request(body: dict) -> tuple[dict, list]:
    if not isinstance(body, dict):
        raise ValidationError("body must be a JSON object")
    overrides = {}
    for key, (lo, hi) in LIMITS.items():
        if key in body and body[key] is not None:
            try:
                val = float(body[key])
            except (TypeError, ValueError):
                raise ValidationError(f"{key} must be a number")
            if not lo <= val <= hi:
                raise ValidationError(f"{key} must be between {lo} and {hi}")
            overrides[key] = val
    hubs = body.get("hubs")
    if hubs is not None and (not isinstance(hubs, list) or not hubs):
        raise ValidationError("hubs must be a non-empty list of hub ids")
    return overrides, hubs


def recommend(designs: dict) -> dict:
    pure_best = min(MODES, key=lambda m: designs[m]["objective"])
    mix, ref = designs["bestmix"], designs[pure_best]
    saving = ref["objective"] - mix["objective"]
    pct = 100.0 * saving / ref["objective"] if ref["objective"] else 0.0
    return {
        "design": "bestmix",
        "best_pure_design": pure_best,
        "saving_vs_best_pure_eur_week": round(saving, 2),
        "saving_vs_best_pure_pct": round(pct, 2),
        "text": (f"Best mix beats {LABELS[pure_best].lower()}, the cheapest single design, by "
                 f"EUR {saving:,.0f} a week ({pct:.1f}%) on cost plus CO2 price."),
    }


def handle_scenario(body: dict, network: dict | None = None) -> dict:
    overrides, hub_ids = parse_request(body)
    net = network or generate()
    if hub_ids is not None:
        known = {h["id"] for h in net["hubs"]}
        unknown = [h for h in hub_ids if h not in known]
        if unknown:
            raise ValidationError(f"unknown hub ids: {unknown}")
        net = {**net, "hubs": [{**h, "active": h["id"] in hub_ids} for h in net["hubs"]]}
    result = run_scenario(net, overrides)
    designs = summary(result)
    mix = result["designs"]["bestmix"]
    return {
        "params": result["params"],
        "designs": designs,
        "recommendation": recommend(designs),
        "supplier_modes": [{"supplier_id": sid, "mode": mode, "hub_id": mix["hub_of"].get(sid)}
                           for sid, mode in sorted(mix["assign"].items())],
    }
