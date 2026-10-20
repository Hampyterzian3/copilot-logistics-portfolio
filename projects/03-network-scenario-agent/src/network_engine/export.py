"""Generate synthetic data and baseline results.

python -m network_engine.export   (run from projects/03-network-scenario-agent/src)

Writes
- ../data/network.json, ../data/suppliers.csv, ../data/baseline_results.csv
- <site>/demos/data/03-baseline.json and 03-baseline.js (same payload, the .js
  form lets the demo load it from file:// without fetch)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .data import generate
from .model import run_scenario, summary

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
SITE_DATA = PROJECT.parent.parent / "site" / "demos" / "data"

CHECK_SCENARIOS = [
    {"name": "baseline", "overrides": {}},
    {"name": "fuel_plus_40", "overrides": {"fuel_index": 1.4}},
    {"name": "co2_120", "overrides": {"co2_price_t": 120}},
    {"name": "cheap_handling_6_stops", "overrides": {"handling_ldm": 3, "max_stops": 6}},
    {"name": "two_stops", "overrides": {"max_stops": 2}},
]


def main() -> None:
    net = generate()
    (PROJECT / "data").mkdir(exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (PROJECT / "data" / "network.json").write_text(json.dumps(net, indent=1), encoding="utf-8")
    with open(PROJECT / "data" / "suppliers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(net["suppliers"][0].keys()))
        w.writeheader()
        w.writerows(net["suppliers"])

    scenarios = []
    rows = []
    for sc in CHECK_SCENARIOS:
        res = run_scenario(net, sc["overrides"])
        summ = summary(res)
        scenarios.append({"name": sc["name"], "overrides": sc["overrides"], "results": summ,
                          "bestmix_assign": res["designs"]["bestmix"]["assign"]})
        for design, r in summ.items():
            rows.append({"scenario": sc["name"], "design": design, **{k: v for k, v in r.items() if k != "mode_counts"}})
    with open(PROJECT / "data" / "baseline_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    payload = {"generated_by": "network_engine.export", "network": net,
               "params": run_scenario(net)["params"], "scenarios": scenarios}
    text = json.dumps(payload, separators=(",", ":"))
    (SITE_DATA / "03-baseline.json").write_text(text, encoding="utf-8")
    (SITE_DATA / "03-baseline.js").write_text("window.NETWORK_BASELINE=" + text + ";\n", encoding="utf-8")
    for sc in scenarios:
        print(sc["name"], {d: (r["cost_week"], r["co2_t_week"], r["trucks_week"]) for d, r in sc["results"].items()})


if __name__ == "__main__":
    main()
