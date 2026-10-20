"""Generate data, score in-transit shipments, run the backtest and export demo files.

Usage: python src/run_pipeline.py
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import generate_data as gen
from alert_card import build_alert_card
from risk_model import BAND_LABELS, BANDS, WEIGHTS, backtest, build_features, compute_rates, score_shipment

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
DATA = PROJECT / "data"
SITE_DATA = REPO / "site" / "demos" / "data"
BACKTEST_CUTOFF = datetime(2026, 8, 1)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%a %d %b %Y, %H:%M")


def run(seed: int = gen.SEED) -> dict:
    d = gen.generate(seed)
    history, live = d["history"], d["in_transit"]
    rates = compute_rates(history)

    records = []
    for s in live:
        rec = build_features(s, rates)
        rec.update({"po_ref": s["po_ref"], "pieces": s["pieces"],
                    "promised_display": fmt_dt(s["promised_time"]),
                    "last_scan_time": (s["snapshot_time"]).strftime("%Y-%m-%dT%H:%M")})
        rec["py"] = score_shipment(rec)
        records.append(rec)
    records.sort(key=lambda r: (-r["py"]["score"], r["shipment_id"]))

    bt = backtest(history, BACKTEST_CUTOFF)
    counts = {b: sum(1 for r in records if r["py"]["band"] == b) for b in BAND_LABELS}
    areas_ranked = sorted(rates["area_loss_rate"].items(), key=lambda kv: -kv[1])

    # ---- data/ ----
    DATA.mkdir(exist_ok=True)
    write_csv(DATA / "areas.csv",
              [{"area": a["area"], "country": a["country"],
                "shipments_12m": rates["area_volume"][a["area"]],
                "loss_rate_12m": rates["area_loss_rate"][a["area"]]} for a in d["areas"]],
              ["area", "country", "shipments_12m", "loss_rate_12m"])
    write_csv(DATA / "lanes.csv",
              [{**l, "delay_rate_12m": rates["lane_delay_rate"][l["lane"]]} for l in d["lanes"] if l["lane"] in rates["lane_delay_rate"]],
              ["lane", "origin", "origin_hub", "dest_country", "customs_required", "base_transit_days", "delay_rate_12m"])
    write_csv(DATA / "carriers.csv",
              [{"carrier": c, "on_time_12m": v} for c, v in sorted(rates["carrier_on_time"].items())],
              ["carrier", "on_time_12m"])
    hist_fields = ["shipment_id", "customer", "lane", "carrier", "area", "snapshot_time", "last_scan",
                   "dwell_hours", "dwell_norm_hours", "customs_status", "days_to_promise",
                   "remaining_transit_days", "non_working_days", "holiday_name", "late", "lost"]
    write_csv(DATA / "history_snapshots.csv",
              [{**h, "snapshot_time": h["snapshot_time"].strftime("%Y-%m-%dT%H:%M")} for h in history], hist_fields)
    write_csv(DATA / "scan_events.csv", d["scan_events"],
              ["shipment_id", "event", "description", "location", "timestamp"])
    score_fields = ["shipment_id", "customer", "po_ref", "carrier", "lane", "area", "score", "band",
                    "reason_1", "reason_2", "reason_3", "lane_delay_rate", "area_loss_rate", "carrier_on_time",
                    "dwell_hours", "dwell_norm_hours", "customs_status", "days_to_promise",
                    "remaining_transit_days", "non_working_days", "holiday_name"]
    write_csv(DATA / "scored_shipments.csv",
              [{**r, "score": r["py"]["score"], "band": r["py"]["band"],
                **{f"reason_{i + 1}": x["text"] for i, x in enumerate(r["py"]["reasons"])}} for r in records],
              score_fields)
    (DATA / "reference_rates.json").write_text(json.dumps(rates, indent=2), encoding="utf-8")
    (DATA / "backtest.json").write_text(json.dumps(bt, indent=2), encoding="utf-8")

    # ---- teams/alert-card.json: highest-scoring critical shipment ----
    top = next(r for r in records if r["py"]["band"] == "critical")
    card = build_alert_card(top, top["py"])
    (PROJECT / "teams" / "alert-card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")

    # ---- site demo data ----
    events = {}
    for e in d["scan_events"]:
        events.setdefault(e["shipment_id"], []).append([e["description"], e["location"], e["timestamp"]])
    demo = {
        "as_of": gen.AS_OF.strftime("%Y-%m-%dT%H:%M"),
        "as_of_display": fmt_dt(gen.AS_OF),
        "model": {"weights": [list(w) for w in WEIGHTS], "bands": [list(b) for b in BANDS]},
        "counts": counts,
        "backtest": bt,
        "network_loss_rate": rates["network_loss_rate"],
        "areas_ranked": [[a, v, rates["area_volume"][a]] for a, v in areas_ranked],
        "carriers": rates["carrier_on_time"],
        "card_example_id": top["shipment_id"],
        "shipments": records,
        "events": events,
    }
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    body = json.dumps(demo, separators=(",", ":"))
    (SITE_DATA / "04-inbound-risk.json").write_text(body, encoding="utf-8")
    (SITE_DATA / "04-inbound-risk.js").write_text(
        "/* Generated by projects/04-inbound-risk-agent/src/run_pipeline.py. Synthetic data. */\n"
        f"window.RISK_DATA = {body};\n", encoding="utf-8")

    return {"counts": counts, "backtest": bt, "top": top["shipment_id"],
            "areas_top2": [a for a, _ in areas_ranked[:2]]}


if __name__ == "__main__":
    out = run()
    bt = out["backtest"]
    print("bands:", out["counts"])
    print("top critical:", out["top"], "| highest-loss areas:", out["areas_top2"])
    print(f"backtest ({bt['test_snapshots']} snapshots from {bt['cutoff']}, late rate {bt['test_late_rate']:.1%}):")
    for k in ("critical", "at_risk_or_above", "watch_or_above"):
        c = bt[k]
        print(f"  {k}: flagged {c['flagged']}, precision {c['precision']:.1%}, recall {c['recall']:.1%}")
