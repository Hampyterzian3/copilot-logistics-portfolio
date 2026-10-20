"""Executive KPI Briefing Copilot: dataset, variance engine and narrative generator.

Contoso Logistics (fictional). Synthetic, seeded, reproducible data only.

Pipeline
    generate_dataset()  -> weekly KPI rows for six top customers x 26 weeks
    compute_variances() -> week-on-week and vs 8-week baseline, z-score, rule flags
    rank_materiality()  -> flagged variances ordered by materiality score
    build_week()        -> facts, brief, slide outline and Teams post for one week

Every generated sentence carries `refs`: ids of facts (numbers) it is built from.
`validate_sentences()` checks that every number in the text comes from a referenced fact.

Run:  python src/briefing.py      (writes data/ and site/demos/data/05-kpi-briefing.json/.js)
"""
from __future__ import annotations

import csv
import json
import math
import random
import re
import statistics
from datetime import date, timedelta
from pathlib import Path

SEED = 505
N_WEEKS = 26
BASELINE_WEEKS = 8
FIRST_WEEK_END = date(2026, 4, 5)  # Sunday, ISO 2026-W14
Z_GATE = 2.0

CUSTOMERS = [
    # id, name, industry, shipments/wk, revenue/shipment EUR, margin, OTP %, claims per 1,000, CO2 kg/shipment
    ("NWA", "Northwind Automotive", "automotive OEM", 1800, 410, 0.14, 96.5, 1.2, 210),
    ("FBS", "Fabrikam Steel", "steel manufacturer", 950, 780, 0.12, 95.0, 2.0, 420),
    ("TSR", "Tailspin Retail", "retail and e-commerce", 3200, 160, 0.09, 97.2, 2.5, 55),
    ("LWC", "Litware Chemicals", "chemicals producer", 700, 920, 0.16, 96.0, 1.5, 380),
    ("AWC", "Adventure Works Consumer", "consumer goods", 2100, 230, 0.11, 95.8, 1.8, 120),
    ("WGP", "Woodgrove Pharma", "pharma and healthcare", 420, 1350, 0.19, 98.4, 0.8, 160),
]

# Seeded events (customer id, metric effect, week indexes 0-based)
EVENTS = [
    {"customer": "FBS", "type": "margin_dip", "weeks": [17, 18, 19],
     "note": "cost-to-serve per shipment up 6.5% (detention and fuel)"},
    {"customer": "TSR", "type": "otp_drop", "weeks": [21, 22],
     "note": "on-time down about 6 pp, claims up 80% (peak-season hub congestion)"},
    {"customer": "NWA", "type": "volume_surge", "weeks": [24, 25],
     "note": "shipments up 28% (production ramp-up)"},
]

# Metric rules. kind: rel = relative %, pp = percentage points, abs = absolute count.
METRICS = {
    "shipments": dict(label="Volume", measure="Shipments", kind="rel", threshold=0.10,
                      better="up", weight=0.7, floor=0.01),
    "revenue": dict(label="Revenue", measure="Revenue", kind="rel", threshold=0.10,
                    better="up", weight=0.9, floor=0.01),
    "cts": dict(label="Cost to serve", measure="Cost to Serve per Shipment", kind="rel", threshold=0.04,
                better="down", weight=0.8, floor=0.005),
    "margin_pct": dict(label="Margin", measure="Margin %", kind="pp", threshold=2.0,
                       better="up", weight=1.0, floor=0.25),
    "otp_pct": dict(label="On-time", measure="OTP %", kind="pp", threshold=2.0,
                    better="up", weight=0.9, floor=0.25),
    "claims": dict(label="Claims", measure="Claims", kind="abs", threshold=5,
                   better="down", weight=0.6, floor=1.0),
    "co2": dict(label="CO2 per shipment", measure="CO2 kg per Shipment", kind="rel", threshold=0.06,
                better="down", weight=0.5, floor=0.01),
}
TAG_HIGH = 5.0
TAG_MEDIUM = 3.0

ROOT = Path(__file__).resolve().parents[1]           # projects/05-kpi-briefing-copilot
SITE = ROOT.parents[1] / "site"                       # R/site


# ---------------------------------------------------------------- dataset
def week_label(i: int) -> str:
    d = FIRST_WEEK_END + timedelta(weeks=i)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_end(i: int) -> str:
    return (FIRST_WEEK_END + timedelta(weeks=i)).isoformat()


def _poisson(rng: random.Random, lam: float) -> int:
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def generate_dataset(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for cid, name, industry, shp0, rps0, m0, otp0, crate, co20 in CUSTOMERS:
        cps0 = rps0 * (1 - m0)
        for i in range(N_WEEKS):
            ev = {e["type"] for e in EVENTS if e["customer"] == cid and i in e["weeks"]}
            shp = shp0 * (1 + 0.002 * i) * (1 + rng.gauss(0, 0.03))
            if "volume_surge" in ev:
                shp *= 1.28
            shp = int(round(shp))
            rps = rps0 * (1 + rng.gauss(0, 0.006))
            cps = cps0 * (1 + rng.gauss(0, 0.006))
            if "margin_dip" in ev:
                cps *= 1.065
            otp = otp0 + rng.gauss(0, 0.45)
            claims_lam = shp * crate / 1000
            if "otp_drop" in ev:
                otp -= 6.0 + rng.gauss(0, 0.4)
                claims_lam *= 1.8
            otp = min(otp, 99.8)
            claims = _poisson(rng, claims_lam)
            co2 = co20 * (1 - 0.001 * i) * (1 + rng.gauss(0, 0.015))
            revenue = shp * rps
            cost = shp * cps
            rows.append({
                "customer_id": cid, "customer": name, "industry": industry,
                "week": week_label(i), "week_end": week_end(i), "week_index": i,
                "shipments": shp,
                "revenue": round(revenue, 2),
                "cost": round(cost, 2),
                "cts": round(cps, 2),
                "margin_pct": round((revenue - cost) / revenue * 100, 2),
                "otp_pct": round(otp, 2),
                "claims": claims,
                "co2": round(co2, 1),
            })
    return rows


def portfolio_rows(rows: list[dict]) -> list[dict]:
    """Portfolio (all six customers) per week. Ratios are recomputed from sums, not averaged."""
    out = []
    for i in range(N_WEEKS):
        wk = [r for r in rows if r["week_index"] == i]
        shp = sum(r["shipments"] for r in wk)
        rev = sum(r["revenue"] for r in wk)
        cost = sum(r["cost"] for r in wk)
        out.append({
            "customer_id": "ALL", "customer": "Top six portfolio", "week": week_label(i), "week_index": i,
            "shipments": shp, "revenue": round(rev, 2), "cost": round(cost, 2),
            "cts": round(cost / shp, 2),
            "margin_pct": round((rev - cost) / rev * 100, 2),
            "otp_pct": round(sum(r["otp_pct"] * r["shipments"] for r in wk) / shp, 2),
            "claims": sum(r["claims"] for r in wk),
            "co2": round(sum(r["co2"] * r["shipments"] for r in wk) / shp, 1),
        })
    return out


# ---------------------------------------------------------------- variance engine
def variance(series: list[float], i: int, metric: str) -> dict:
    """Variance of series[i] vs series[i-1] (WoW) and vs the median of the previous 8 weeks (baseline)."""
    cfg = METRICS[metric]
    v, prev = series[i], series[i - 1]
    base_window = series[i - BASELINE_WEEKS:i]
    base = statistics.median(base_window)
    # robust spread: 1.4826 x median absolute deviation, so one event week does not mask the next
    sd = 1.4826 * statistics.median(abs(x - base) for x in base_window)
    floor = cfg["floor"] * abs(base) if cfg["kind"] == "rel" else cfg["floor"]
    z = (v - base) / max(sd, floor)
    if cfg["kind"] == "rel":
        wow, vs_base = (v - prev) / prev, (v - base) / base
    else:
        wow, vs_base = v - prev, v - base
    breach = abs(vs_base) >= cfg["threshold"]
    flagged = breach and abs(z) >= Z_GATE
    up = v > base
    favourable = up if cfg["better"] == "up" else not up
    return {"value": v, "prev": prev, "baseline": base, "sd": sd, "wow": wow, "vs_base": vs_base,
            "z": z, "breach": breach, "flagged": flagged, "favourable": favourable}


def materiality_score(z: float, metric: str, revenue_share: float) -> float:
    """|z| (capped at 8) x metric weight x size factor. Size factor is 1.0 for an average-sized customer."""
    size = math.sqrt(max(revenue_share, 0.0) * len(CUSTOMERS))
    return round(min(abs(z), 8.0) * METRICS[metric]["weight"] * size, 2)


def materiality_tag(score: float) -> str:
    return "High" if score >= TAG_HIGH else "Medium" if score >= TAG_MEDIUM else "Low"


def compute_variances(rows: list[dict], i: int) -> list[dict]:
    """All customer x metric variances for week index i (needs i >= BASELINE_WEEKS)."""
    if i < BASELINE_WEEKS:
        raise ValueError("week index must leave an 8-week baseline")
    by_c = {c[0]: sorted([r for r in rows if r["customer_id"] == c[0]], key=lambda r: r["week_index"])
            for c in CUSTOMERS}
    base_rev = {cid: statistics.fmean(r["revenue"] for r in rs[i - BASELINE_WEEKS:i]) for cid, rs in by_c.items()}
    total = sum(base_rev.values())
    out = []
    for cid, rs in by_c.items():
        share = base_rev[cid] / total
        for m in METRICS:
            var = variance([r[m] for r in rs], i, m)
            var.update(customer_id=cid, customer=rs[0]["customer"], metric=m, revenue_share=share,
                       score=materiality_score(var["z"], m, share))
            var["tag"] = materiality_tag(var["score"]) if var["flagged"] else None
            out.append(var)
    return out


def rank_materiality(variances: list[dict]) -> list[dict]:
    """Flagged variances only, highest materiality first (ties: larger customer, then name)."""
    flagged = [v for v in variances if v["flagged"]]
    return sorted(flagged, key=lambda v: (-v["score"], -v["revenue_share"], v["customer"], v["metric"]))


def margin_bridge(rows: list[dict], cid: str, i: int) -> dict:
    """Split margin change vs baseline into a rate effect (revenue per shipment) and a cost effect."""
    rs = sorted([r for r in rows if r["customer_id"] == cid], key=lambda r: r["week_index"])
    win = rs[i - BASELINE_WEEKS:i]
    rps_b = sum(r["revenue"] for r in win) / sum(r["shipments"] for r in win)
    cps_b = sum(r["cost"] for r in win) / sum(r["shipments"] for r in win)
    now = rs[i]
    rps_n, cps_n = now["revenue"] / now["shipments"], now["cost"] / now["shipments"]
    m_b = (1 - cps_b / rps_b) * 100
    m_rate = (1 - cps_b / rps_n) * 100
    m_n = (1 - cps_n / rps_n) * 100
    return {"margin_base": m_b, "margin_now": m_n, "rate_effect": m_rate - m_b, "cost_effect": m_n - m_rate,
            "rps_base": rps_b, "rps_now": rps_n, "cps_base": cps_b, "cps_now": cps_n}


# ---------------------------------------------------------------- formatting
def fmt_value(m: str, v: float) -> str:
    if m == "revenue":
        return f"€{v / 1e6:.2f}m"
    if m == "shipments":
        return f"{int(round(v)):,}"
    if m == "cts":
        return f"€{v:,.0f}"
    if m in ("margin_pct", "otp_pct"):
        return f"{v:.1f}%"
    if m == "claims":
        return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"
    if m == "co2":
        return f"{v:.0f} kg"
    raise KeyError(m)


def fmt_delta(m: str, d: float) -> str:
    kind = METRICS[m]["kind"]
    if kind == "rel":
        return f"{abs(d) * 100:.1f}%"
    if kind == "pp":
        return f"{abs(d):.1f} pp"
    return f"{abs(d):.0f}" if abs(d - round(d)) < 0.05 else f"{abs(d):.1f}"


def direction(d: float) -> str:
    return "up" if d > 0 else "down" if d < 0 else "flat"


def move(m: str, d: float) -> str:
    """'up 1.3%', 'down 0.4 pp', or 'flat' when the change rounds to zero at display precision."""
    txt = fmt_delta(m, d)
    return "flat" if float(re.sub(r"[^0-9.]", "", txt)) == 0 else f"{direction(d)} {txt}"


NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def number_tokens(text: str) -> set[str]:
    return set(NUM_RE.findall(text.replace("CO2", "CO_")))  # chemical name, not a figure


# ---------------------------------------------------------------- narrative
class FactBook:
    """Numbers the narrative may use. Each fact maps to a DAX measure in the semantic model."""

    def __init__(self, week: str):
        self.week = week
        self.facts: dict[str, dict] = {}

    def add(self, customer: str, metric: str, var: dict | None = None, value: float | None = None,
            measure: str | None = None, extra: dict | None = None) -> str:
        fid = f"F{len(self.facts) + 1:02d}"
        cfg = METRICS.get(metric, {})
        val = var["value"] if var else value
        f = {"id": fid, "week": self.week, "customer": customer, "metric": metric,
             "measure": measure or cfg.get("measure", metric),
             "value": round(val, 4), "value_fmt": fmt_value(metric, val) if metric in METRICS else str(val)}
        if var:
            f.update(baseline=round(var["baseline"], 4), baseline_fmt=fmt_value(metric, var["baseline"]),
                     prev_fmt=fmt_value(metric, var["prev"]),
                     wow_fmt=fmt_delta(metric, var["wow"]), vs_base_fmt=fmt_delta(metric, var["vs_base"]),
                     vs_base_dir=direction(var["vs_base"]), wow_dir=direction(var["wow"]),
                     wow_mv_fmt=move(metric, var["wow"]), base_mv_fmt=move(metric, var["vs_base"]),
                     z=round(var["z"], 2), z_fmt=f"{abs(var['z']):.1f}",
                     score=var.get("score"), tag=var.get("tag"))
        if extra:
            f.update(extra)
        self.facts[fid] = f
        return fid

    def displays(self, fid: str) -> list[str]:
        f = self.facts[fid]
        return [f["week"]] + [str(v) for k, v in f.items() if k.endswith("_fmt")]


def S(text: str, *refs: str) -> dict:
    return {"text": text, "refs": list(refs)}


def validate_sentences(sentences: list[dict], book: FactBook) -> list[str]:
    """Return problems: sentences without refs, unknown refs, or numbers not found in referenced facts."""
    problems = []
    for s in sentences:
        if not s["refs"]:
            problems.append(f"no refs: {s['text']}")
            continue
        missing = [r for r in s["refs"] if r not in book.facts]
        if missing:
            problems.append(f"unknown refs {missing}: {s['text']}")
            continue
        allowed = set()
        for r in s["refs"]:
            for d in book.displays(r):
                allowed |= number_tokens(d)
        stray = number_tokens(s["text"]) - allowed
        if stray:
            problems.append(f"unsupported numbers {sorted(stray)}: {s['text']}")
    return problems


def _var_phrase(f: dict) -> str:
    return f"{f['base_mv_fmt']} against the eight-week baseline of {f['baseline_fmt']}"


def _thing_sentence(f: dict) -> str:
    label = METRICS[f["metric"]]["label"]
    return f"{f['customer']}: {label.lower()} {f['value_fmt']}, {_var_phrase(f)} ({f['tag']} materiality)."


def _action(f: dict, book: FactBook, cid_facts: dict) -> dict:
    c, m, fav = f["customer"], f["metric"], f["favourable"]
    cts = cid_facts.get("cts")
    if m in ("margin_pct", "cts") and not fav:
        ref = book.facts[cts] if cts else f
        return S(f"Ask the {c} account lead to review cost to serve ({ref['value_fmt']} per shipment against "
                 f"{ref['baseline_fmt']}) and check surcharge recovery before the next rate review.", ref["id"])
    if m in ("otp_pct", "claims") and not fav:
        otp = book.facts[cid_facts["otp_pct"]]
        cl = book.facts[cid_facts["claims"]]
        return S(f"Open a service recovery review with operations for {c}: on-time {otp['value_fmt']} against "
                 f"{otp['baseline_fmt']}, with {cl['value_fmt']} claims this week.", otp["id"], cl["id"])
    if m in ("shipments", "revenue") and fav:
        shp = book.facts[cid_facts["shipments"]]
        return S(f"Confirm capacity and carrier allocation with {c}: {shp['value_fmt']} shipments this week, "
                 f"{shp['vs_base_fmt']} above baseline. Ask whether the uplift continues.", shp["id"])
    if m in ("shipments", "revenue"):
        shp = book.facts[cid_facts["shipments"]]
        return S(f"Check with {c} whether the {shp['vs_base_fmt']} volume drop is a forecast change or lost share.",
                 shp["id"])
    if m == "co2" and not fav:
        return S(f"Review load fill and mode mix for {c}: CO2 per shipment {f['value_fmt']} against "
                 f"{f['baseline_fmt']}.", f["id"])
    return S(f"Share the {METRICS[m]['label'].lower()} improvement for {c} ({f['value_fmt']}) with the account "
             f"team and confirm what drove it.", f["id"])


def build_week(rows: list[dict], i: int) -> dict:
    wk = week_label(i)
    book = FactBook(wk)
    variances = compute_variances(rows, i)
    ranked = rank_materiality(variances)

    # portfolio facts
    port = portfolio_rows(rows)
    pf = {m: book.add("Top six portfolio", m, variance([p[m] for p in port], i, m)) for m in METRICS}

    # customer facts (all metrics, so callouts and agent answers are traceable)
    cf: dict[str, dict[str, str]] = {}
    for v in variances:
        cf.setdefault(v["customer_id"], {})[v["metric"]] = book.add(v["customer"], v["metric"], v)
        book.facts[cf[v["customer_id"]][v["metric"]]]["favourable"] = v["favourable"]
        book.facts[cf[v["customer_id"]][v["metric"]]]["flagged"] = v["flagged"]
    ranked_facts = [book.facts[cf[v["customer_id"]][v["metric"]]] for v in ranked]

    # margin bridge facts per customer (pooled eight-week revenue and cost per shipment)
    bridges = {}
    for cid, name, *_ in CUSTOMERS:
        b = margin_bridge(rows, cid, i)
        bridges[cid] = {k: round(v, 3) for k, v in b.items()}
        pp = lambda x: f"{abs(x):.1f} pp"
        bridges[cid]["facts"] = {
            "rps": book.add(name, "bridge_rps", value=b["rps_now"], measure="Revenue per Shipment",
                            extra={"value_fmt": f"€{b['rps_now']:,.0f}", "baseline_fmt": f"€{b['rps_base']:,.0f}"}),
            "cps": book.add(name, "bridge_cps", value=b["cps_now"], measure="Cost to Serve per Shipment",
                            extra={"value_fmt": f"€{b['cps_now']:,.0f}", "baseline_fmt": f"€{b['cps_base']:,.0f}"}),
            "rate": book.add(name, "bridge_rate", value=b["rate_effect"], measure="Margin Rate Effect pp",
                             extra={"value_fmt": pp(b["rate_effect"]), "dir": direction(b["rate_effect"])}),
            "cost": book.add(name, "bridge_cost", value=b["cost_effect"], measure="Margin Cost Effect pp",
                             extra={"value_fmt": pp(b["cost_effect"]), "dir": direction(b["cost_effect"])}),
        }

    # three things that matter: distinct customers among High/Medium first, then other High/Medium, then Low
    things = []
    passes = [lambda f: f["tag"] != "Low" and f["customer"] not in {t["customer"] for t in things},
              lambda f: f["tag"] != "Low", lambda f: True]
    for ok in passes:
        for f in ranked_facts:
            if len(things) < 3 and f not in things and ok(f):
                things.append(f)

    rev, mar, otp = book.facts[pf["revenue"]], book.facts[pf["margin_pct"]], book.facts[pf["otp_pct"]]
    if things:
        top = things[0]
        headline = S(f"Week {wk}: portfolio revenue {rev['value_fmt']}, {rev['wow_mv_fmt']} on last week. "
                     f"Biggest mover: {top['customer']} {METRICS[top['metric']]['label'].lower()} "
                     f"{top['base_mv_fmt']} against baseline.", rev["id"], top["id"])
    else:
        headline = S(f"Week {wk}: portfolio revenue {rev['value_fmt']}, {rev['wow_mv_fmt']} on last week, "
                     f"with no material variances across the six customers.", rev["id"])
    summary = S(f"Portfolio margin {mar['value_fmt']} ({_var_phrase(mar)}); on-time {otp['value_fmt']} "
                f"({otp['base_mv_fmt']}).", mar["id"], otp["id"])

    thing_sents = [S(_thing_sentence(f), f["id"]) for f in things]
    if not thing_sents:
        thing_sents = [S(f"No customer breached a threshold in {wk}; margin and on-time are within normal range.",
                         mar["id"], otp["id"])]

    callouts = []
    for cid, name, *_ in CUSTOMERS:
        fs = {m: book.facts[cf[cid][m]] for m in METRICS}
        flagged = [f for f in ranked_facts if f["customer"] == name]
        base = (f"{name}: revenue {fs['revenue']['value_fmt']}, margin {fs['margin_pct']['value_fmt']}, "
                f"on-time {fs['otp_pct']['value_fmt']}.")
        refs = [fs["revenue"]["id"], fs["margin_pct"]["id"], fs["otp_pct"]["id"]]
        if flagged:
            f0 = flagged[0]
            base += f" Watch {METRICS[f0['metric']]['label'].lower()}: {_var_phrase(f0)}."
            if f0["id"] not in refs:
                refs.append(f0["id"])
            status = f0["tag"]
        else:
            base += " Steady, no threshold breached."
            status = "Steady"
        callouts.append({**S(base, *refs), "customer": name, "status": status})

    actions, acted = [], set()
    for f in ranked_facts:
        if f["tag"] == "Low" or f["customer"] in acted:
            continue
        cid = next(c[0] for c in CUSTOMERS if c[1] == f["customer"])
        actions.append(_action(f, book, cf[cid]))
        acted.add(f["customer"])
        if len(actions) == 4:
            break
    if not actions:
        actions = [S(f"No escalation needed for {wk}; keep the standard account reviews.", rev["id"])]

    # slide outline (5 slides)
    shp, cl, co2 = book.facts[pf["shipments"]], book.facts[pf["claims"]], book.facts[pf["co2"]]
    deep = things[0] if things else None
    slides = [
        {"n": 1, "title": "Portfolio at a glance", "visual": "KPI card row with 26-week sparklines",
         "bullets": [headline, S(f"Shipments {shp['value_fmt']} ({shp['wow_mv_fmt']} week on week).", shp["id"]), summary]},
        {"n": 2, "title": "Three things that matter", "visual": "Ranked variance table with materiality tags",
         "bullets": thing_sents},
        {"n": 3, "title": f"Deep dive: {deep['customer']}" if deep else "Deep dive: none required",
         "visual": "Line chart, metric against eight-week baseline band",
         "bullets": [S(_thing_sentence(deep), deep["id"])] + [
             c for c in callouts if c["customer"] == deep["customer"]] if deep else
         [S(f"All customers within thresholds in {wk}.", rev["id"])]},
        {"n": 4, "title": "Service and sustainability", "visual": "On-time and CO2 small multiples by customer",
         "bullets": [S(f"Portfolio on-time {otp['value_fmt']}, {_var_phrase(otp)}.", otp["id"]),
                     S(f"Claims {cl['value_fmt']} this week, {cl['wow_mv_fmt']} on last week.", cl["id"]),
                     S(f"CO2 per shipment {co2['value_fmt']}, {_var_phrase(co2)}.", co2["id"])]},
        {"n": 5, "title": "Decisions and actions", "visual": "Action list with owners and due dates",
         "bullets": actions},
    ]
    for s in slides:  # strip extra keys from callouts reused as bullets
        s["bullets"] = [{"text": b["text"], "refs": b["refs"]} for b in s["bullets"]]

    teams = {
        "title": f"Weekly account brief {wk}: draft for approval",
        "lines": [headline] + [S(t["text"], *t["refs"]) for t in thing_sents],
        "footer": "Draft brief (Word) and deck outline (PowerPoint) attached. Not sent to leadership until an analyst approves.",
    }

    brief = {"headline": headline, "summary": summary, "things": thing_sents, "callouts": callouts,
             "actions": actions}
    all_sents = [headline, summary, *thing_sents, *callouts, *actions,
                 *[b for s in slides for b in s["bullets"]], *teams["lines"]]
    problems = validate_sentences(all_sents, book)
    if problems:
        raise AssertionError("untraceable sentences:\n" + "\n".join(problems))

    var_table = [{
        "rank": n + 1, "customer": v["customer"], "customer_id": v["customer_id"], "metric": v["metric"],
        "label": METRICS[v["metric"]]["label"], "value_fmt": fmt_value(v["metric"], v["value"]),
        "baseline_fmt": fmt_value(v["metric"], v["baseline"]),
        "wow": round(v["wow"], 4), "vs_base": round(v["vs_base"], 4), "kind": METRICS[v["metric"]]["kind"],
        "z": round(v["z"], 2), "score": v["score"], "tag": v["tag"], "favourable": v["favourable"],
        "fact": cf[v["customer_id"]][v["metric"]],
    } for n, v in enumerate(ranked)]

    return {"week": wk, "week_end": week_end(i), "index": i, "facts": book.facts, "portfolio": pf,
            "customer_facts": cf, "variances": var_table, "brief": brief, "slides": slides, "teams": teams,
            "bridges": bridges, "sentence_count": len(all_sents)}


# ---------------------------------------------------------------- export
def brief_markdown(w: dict) -> str:
    b = w["brief"]
    ref = lambda s: f"{s['text']} [{', '.join(s['refs'])}]"
    lines = [f"# Weekly account brief {w['week']} (draft)", "", ref(b["headline"]), "", ref(b["summary"]), "",
             "## Three things that matter", *[f"- {ref(s)}" for s in b["things"]], "",
             "## Customer callouts", *[f"- {ref(s)}" for s in b["callouts"]], "",
             "## Actions", *[f"- {ref(s)}" for s in b["actions"]], "", "## Sources", ""]
    for f in w["facts"].values():
        lines.append(f"- {f['id']}: [{f['measure']}] {f['customer']} {f['week']} = {f['value_fmt']}"
                     + (f" (baseline {f['baseline_fmt']}" + (f", z {f['z']})" if "z" in f else ")") if "baseline_fmt" in f else ""))
    return "\n".join(lines) + "\n"


def export(out_json: Path | None = None) -> dict:
    rows = generate_dataset()
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    cols = list(rows[0].keys())
    with open(data_dir / "kpi_weekly.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)

    weeks = {}
    var_rows = []
    for i in range(BASELINE_WEEKS, N_WEEKS):
        w = build_week(rows, i)
        weeks[w["week"]] = w
        for v in w["variances"]:
            var_rows.append({"week": w["week"], **{k: v[k] for k in
                            ("rank", "customer", "metric", "value_fmt", "baseline_fmt", "vs_base", "z", "score", "tag")}})
    with open(data_dir / "variances_flagged.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(var_rows[0].keys()))
        wr.writeheader()
        wr.writerows(var_rows)
    latest = weeks[week_label(N_WEEKS - 1)]
    (data_dir / f"brief_{latest['week']}.md").write_text(brief_markdown(latest), encoding="utf-8")

    series = {}
    for cid, *_ in CUSTOMERS:
        rs = sorted([r for r in rows if r["customer_id"] == cid], key=lambda r: r["week_index"])
        series[cid] = {m: [r[m] for r in rs] for m in METRICS}
    port = portfolio_rows(rows)
    series["ALL"] = {m: [p[m] for p in port] for m in METRICS}

    payload = {
        "meta": {"company": "Contoso Logistics", "seed": SEED, "baseline_weeks": BASELINE_WEEKS, "z_gate": Z_GATE,
                 "tag_high": TAG_HIGH, "tag_medium": TAG_MEDIUM, "events": EVENTS,
                 "note": "Synthetic data. Generated by projects/05-kpi-briefing-copilot/src/briefing.py"},
        "metrics": {m: {k: c[k] for k in ("label", "measure", "kind", "threshold", "better", "weight")}
                    for m, c in METRICS.items()},
        "customers": [{"id": c[0], "name": c[1], "industry": c[2]} for c in CUSTOMERS],
        "weeks": [week_label(i) for i in range(N_WEEKS)],
        "series": series,
        "briefs": weeks,
    }
    out_json = out_json or SITE / "demos" / "data" / "05-kpi-briefing.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    out_json.write_text(blob, encoding="utf-8")
    # same payload as a script, so the demo also works from file:// where fetch() is blocked
    out_json.with_suffix(".js").write_text(f"window.KPI_BRIEFING={blob};\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = export()
    for wk, w in p["briefs"].items():
        top = w["variances"][:3]
        print(wk, len(w["variances"]), "flagged |", "; ".join(f"{v['customer']} {v['label']} {v['tag']} {v['score']}" for v in top))
