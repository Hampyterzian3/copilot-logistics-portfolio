"""Tender Desk RFQ checker.

Reads an RFQ pack (lanes.csv + requirements.md) and returns:
  scope      extracted scope summary (countries, modes, volumes, corridors)
  summary    gap counts and readiness
  lanes      one row per lane with suggested mode and rule flags
  gaps       gap list with rule id and severity
  questions  clarification questions grouped by theme
  outline    solution-design outline (mode band per lane, next steps)

The same rules are ported to JavaScript in site/demos/01-tender-desk-copilot.html
(between RULES-START and RULES-END). check_parity.js asserts both give identical output,
so keep every threshold, message and ordering in step when editing either side.

Usage:
  python src/rfq_checker.py data/northwind-europe-2027            # JSON to stdout
  python src/rfq_checker.py data/northwind-europe-2027 --markdown  # readable report
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

INCOTERMS_2020 = {"EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF"}
SEA_ONLY = {"FAS", "FOB", "CFR", "CIF"}
ROAD_KM_PER_DAY = 650          # single-driver road planning figure under EU driving-time rules
FTL_MIN_PALLETS = 22           # average pallets per shipment from which a full truck is the base case
MULTIMODAL_MIN_KM = 1100       # long-haul threshold where road-rail is worth testing
MULTIMODAL_MIN_SHIPMENTS = 52  # at least weekly, so a rail slot can be filled
DIM_FIELDS = ("pallet_length_cm", "pallet_width_cm", "pallet_height_cm")
SEVERITIES = ("high", "medium", "low")

RULES = {
    "R01": ("Missing annual volume", "high", "Volumes and forecasts"),
    "R02": ("Missing pallet dimensions", "medium", "Packaging and handling"),
    "R03": ("Unclear Incoterm", "medium", "Commercial terms"),
    "R04": ("Sea-only Incoterm on a road lane", "low", "Commercial terms"),
    "R05": ("Hazardous goods without UN number", "high", "Dangerous goods"),
    "R06": ("Unrealistic transit time", "high", "Service levels"),
    "R07": ("Duplicate lane", "medium", "Lane data quality"),
    "R08": ("Requirements section missing", "medium", "Requirements document"),
    "R09": ("Open item marked TBC", "low", "Requirements document"),
}
THEMES = [
    "Volumes and forecasts", "Packaging and handling", "Dangerous goods", "Service levels",
    "Commercial terms", "Lane data quality", "Requirements document",
]
REQUIRED_SECTIONS = [
    ("Contract period", ("contract period", "contract term")),
    ("Service levels", ("service level", "kpi")),
    ("Pricing format", ("pricing", "rate card")),
    ("Fuel mechanism", ("fuel",)),
    ("Liability and insurance", ("liability", "insurance")),
    ("Invoicing and payment", ("invoic", "payment")),
]
BANDS = ["FTL", "Multimodal (road-rail)", "LTL/groupage", "Pending data"]
BAND_RATIONALE = {
    "FTL": f"{FTL_MIN_PALLETS}+ pallets per shipment: dedicated or contracted full trucks.",
    "Multimodal (road-rail)": f"Full loads over {MULTIMODAL_MIN_KM} km at least weekly: test road-rail for cost and CO2.",
    "LTL/groupage": f"Under {FTL_MIN_PALLETS} pallets per shipment: consolidate through groupage hubs.",
    "Pending data": "Volume missing: band assigned once the shipper confirms volumes.",
}


def to_int(value) -> int | None:
    s = (value or "").strip()
    return int(s) if re.fullmatch(r"\d+", s) else None


def min_transit_days(km: int) -> int:
    return max(1, -(-km // ROAD_KM_PER_DAY))


def make_gap(rule_id: str, lane_id, field: str, message: str, detail=None) -> dict:
    name, severity, theme = RULES[rule_id]
    return {"rule_id": rule_id, "rule": name, "severity": severity, "theme": theme,
            "lane_id": lane_id, "field": field, "message": message, "detail": detail}


def lane_gaps(row: dict, seen: dict) -> list[dict]:
    lid = row["lane_id"].strip()
    gaps = []

    # R01 missing annual volume
    missing = [f for f in ("annual_shipments", "pallets_per_shipment") if not to_int(row.get(f))]
    if missing:
        gaps.append(make_gap("R01", lid, ", ".join(missing),
                             f"No usable annual volume ({', '.join(missing)} blank)."))

    # R02 missing pallet dimensions
    missing = [f for f in DIM_FIELDS if not to_int(row.get(f))]
    if missing:
        gaps.append(make_gap("R02", lid, ", ".join(missing),
                             f"Pallet dimensions incomplete ({', '.join(missing)} blank)."))

    # R03 / R04 Incoterms
    raw = (row.get("incoterm") or "").strip()
    token = raw.split()[0].upper() if raw else ""
    if not raw:
        gaps.append(make_gap("R03", lid, "incoterm", "Incoterm blank."))
    elif token not in INCOTERMS_2020:
        gaps.append(make_gap("R03", lid, "incoterm",
                             f"Incoterm '{raw}' is not a valid Incoterms 2020 rule."))
    elif token in SEA_ONLY:
        gaps.append(make_gap("R04", lid, "incoterm",
                             f"Incoterm {token} is for sea and inland waterway only; this lane moves by road."))

    # R05 hazardous goods without a valid UN number
    hazardous = (row.get("hazardous") or "").strip().upper() in ("Y", "YES")
    un_raw = (row.get("un_number") or "").strip()
    if hazardous and not re.fullmatch(r"UN\d{4}", un_raw.upper()):
        msg = ("Hazardous goods flagged but UN number blank." if not un_raw
               else f"Hazardous goods flagged but UN number '{un_raw}' is not in UNnnnn format.")
        gaps.append(make_gap("R05", lid, "un_number", msg))

    # R06 unrealistic transit time
    km = to_int(row.get("distance_km"))
    days = to_int(row.get("required_transit_days"))
    if km is not None and days is not None and days < min_transit_days(km):
        gaps.append(make_gap("R06", lid, "required_transit_days",
                             f"{days} day(s) requested for {km} km; road minimum is about "
                             f"{min_transit_days(km)} day(s) at {ROAD_KM_PER_DAY} km per day."))

    # R07 duplicate lane (same origin and destination city)
    oc, ocity = row["origin_country"].strip().upper(), row["origin_city"].strip()
    dc, dcity = row["dest_country"].strip().upper(), row["dest_city"].strip()
    key = "|".join([oc, ocity.lower(), dc, dcity.lower()])
    if key in seen:
        gaps.append(make_gap("R07", lid, "lane",
                             f"Same corridor as {seen[key]} ({ocity} to {dcity}).", seen[key]))
    else:
        seen[key] = lid
    return gaps


def document_gaps(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").split("\n")
    headings = []
    for line in lines:
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            headings.append(m.group(1).strip().lower())
    gaps = []
    for name, keywords in REQUIRED_SECTIONS:
        if not any(k in h for h in headings for k in keywords):
            gaps.append(make_gap("R08", None, "requirements", f"No section covering {name.lower()}.", name))
    for line in lines:
        if re.search(r"\b(TBC|TBD)\b", line):
            snippet = re.sub(r"^[-*#\s]+", "", line.strip())
            gaps.append(make_gap("R09", None, "requirements", f'Open item: "{snippet}"', snippet))
    return gaps


def suggest_mode(km, shipments, pps) -> str:
    if not shipments or not pps:
        return "Pending data"
    if pps >= FTL_MIN_PALLETS and (km or 0) >= MULTIMODAL_MIN_KM and shipments >= MULTIMODAL_MIN_SHIPMENTS:
        return "Multimodal (road-rail)"
    if pps >= FTL_MIN_PALLETS:
        return "FTL"
    return "LTL/groupage"


def build_questions(gaps: list[dict]) -> list[dict]:
    def ids(rule):
        return ", ".join(g["lane_id"] for g in gaps if g["rule_id"] == rule)

    out = []
    for theme in THEMES:
        tg = [g for g in gaps if g["theme"] == theme]
        rules = [r for r in RULES if any(g["rule_id"] == r for g in tg)]
        qs = []
        for r in rules:
            if r == "R01":
                qs.append(f"Please confirm annual shipments and average pallets per shipment for lanes {ids(r)}. "
                          "A forecast by quarter would help us size capacity.")
            elif r == "R02":
                qs.append(f"Please share pallet length, width and height for lanes {ids(r)}, "
                          "and confirm whether the loads are stackable.")
            elif r == "R03":
                qs.append(f"Please confirm the Incoterms 2020 rule and named place for lanes {ids(r)}.")
            elif r == "R04":
                qs.append(f"Lanes {ids(r)} use a sea-only Incoterm on a road movement. "
                          "Would FCA or DAP reflect the intended handover point?")
            elif r == "R05":
                qs.append(f"Lanes {ids(r)} are flagged as hazardous. Please provide the UN number, "
                          "ADR class and packing group for each product.")
            elif r == "R06":
                qs.append(f"The transit times requested on lanes {ids(r)} are shorter than a single-driver "
                          "road service allows. Can these be relaxed, or should we price a double-manned option?")
            elif r == "R07":
                for g in tg:
                    if g["rule_id"] == r:
                        qs.append(f"Lane {g['lane_id']} appears to repeat lane {g['detail']}. "
                                  "Should these be merged, or do they differ in product or service?")
            elif r == "R08":
                names = ", ".join(g["detail"].lower() for g in tg if g["rule_id"] == r)
                qs.append(f"The requirements document has no section on {names}. "
                          "Please share your expectations so we can reflect them in our offer.")
            elif r == "R09":
                items = "; ".join(g["detail"] for g in tg if g["rule_id"] == r)
                qs.append(f"Please confirm the open items in the requirements: {items}")
        if qs:
            out.append({"theme": theme, "questions": qs})
    return out


def check(rows: list[dict], requirements: str) -> dict:
    seen: dict = {}
    gaps: list[dict] = []
    lanes: list[dict] = []
    for row in rows:
        lg = lane_gaps(row, seen)
        gaps.extend(lg)
        km = to_int(row.get("distance_km"))
        shipments = to_int(row.get("annual_shipments"))
        pps = to_int(row.get("pallets_per_shipment"))
        flags = [g["rule_id"] for g in lg]
        worst = next((s for s in SEVERITIES if any(g["severity"] == s for g in lg)), None)
        lanes.append({
            "lane_id": row["lane_id"].strip(),
            "origin": f"{row['origin_city'].strip()}, {row['origin_country'].strip().upper()}",
            "destination": f"{row['dest_city'].strip()}, {row['dest_country'].strip().upper()}",
            "corridor": f"{row['origin_country'].strip().upper()}-{row['dest_country'].strip().upper()}",
            "distance_km": km,
            "annual_shipments": shipments,
            "pallets_per_shipment": pps,
            "annual_pallets": shipments * pps if shipments and pps else None,
            "hazardous": (row.get("hazardous") or "").strip().upper() in ("Y", "YES"),
            "incoterm": (row.get("incoterm") or "").strip(),
            "mode_requested": (row.get("mode_requested") or "").strip(),
            "required_transit_days": to_int(row.get("required_transit_days")),
            "mode_suggested": suggest_mode(km, shipments, pps),
            "flags": flags,
            "worst": worst,
        })
    gaps.extend(document_gaps(requirements))

    # Scope
    origins = sorted({l["corridor"].split("-")[0] for l in lanes})
    dests = sorted({l["corridor"].split("-")[1] for l in lanes})
    modes: dict = {}
    for l in lanes:
        modes[l["mode_requested"]] = modes.get(l["mode_requested"], 0) + 1
    corridor_pallets: dict = {}
    for l in lanes:
        if l["annual_pallets"]:
            corridor_pallets[l["corridor"]] = corridor_pallets.get(l["corridor"], 0) + l["annual_pallets"]
    top = sorted(corridor_pallets.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    distances = [l["distance_km"] for l in lanes if l["distance_km"] is not None]
    scope = {
        "lane_count": len(lanes),
        "countries": sorted(set(origins) | set(dests)),
        "origin_countries": origins,
        "destination_countries": dests,
        "modes_requested": modes,
        "lanes_with_volume": sum(1 for l in lanes if l["annual_pallets"]),
        "annual_pallets_known": sum(l["annual_pallets"] or 0 for l in lanes),
        "annual_shipments_known": sum(l["annual_shipments"] or 0 for l in lanes),
        "hazardous_lanes": sum(1 for l in lanes if l["hazardous"]),
        "distance_km_min": min(distances) if distances else None,
        "distance_km_max": max(distances) if distances else None,
        "top_corridors": [{"corridor": c, "annual_pallets": p} for c, p in top],
    }

    # Summary
    counts = {s: sum(1 for g in gaps if g["severity"] == s) for s in SEVERITIES}
    flagged = sum(1 for l in lanes if l["flags"])
    summary = {
        "gaps_total": len(gaps), "gaps_by_severity": counts,
        "gaps_by_rule": {r: sum(1 for g in gaps if g["rule_id"] == r) for r in RULES},
        "lanes_with_gaps": flagged, "clean_lanes": len(lanes) - flagged,
        "readiness_pct": (100 * (len(lanes) - flagged)) // len(lanes) if lanes else 0,
        "document_gaps": sum(1 for g in gaps if g["lane_id"] is None),
    }

    # Outline
    bands = []
    for b in BANDS:
        bl = [l for l in lanes if l["mode_suggested"] == b]
        bands.append({"band": b, "lane_count": len(bl), "annual_pallets": sum(l["annual_pallets"] or 0 for l in bl),
                      "lanes": [l["lane_id"] for l in bl], "rationale": BAND_RATIONALE[b]})
    by_band = {b["band"]: b["lane_count"] for b in bands}
    steps = []
    if counts["high"]:
        steps.append(f"Resolve {counts['high']} high-severity gaps with the shipper before pricing.")
    if by_band["FTL"]:
        steps.append(f"Price {by_band['FTL']} FTL lanes on contracted capacity with round-trip matching.")
    if by_band["Multimodal (road-rail)"]:
        steps.append(f"Test road-rail on {by_band['Multimodal (road-rail)']} long-haul lanes against an FTL baseline.")
    if by_band["LTL/groupage"]:
        steps.append(f"Consolidate {by_band['LTL/groupage']} part-load lanes through groupage hubs.")
    if scope["hazardous_lanes"]:
        steps.append(f"Confirm ADR-certified capacity for {scope['hazardous_lanes']} hazardous lanes.")
    outline = {"bands": bands, "next_steps": steps}

    return {"scope": scope, "summary": summary, "lanes": lanes, "gaps": gaps,
            "questions": build_questions(gaps), "outline": outline}


def load_pack(folder: Path) -> tuple[list[dict], str, dict]:
    with (folder / "lanes.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    req = (folder / "requirements.md").read_text(encoding="utf-8")
    meta_path = folder / "pack.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"id": folder.name}
    return rows, req, meta


def to_markdown(meta: dict, result: dict) -> str:
    s, sm = result["scope"], result["summary"]
    out = [f"# RFQ check: {meta.get('shipper', '')} {meta.get('title', meta['id'])}".strip(), "",
           "## Scope",
           f"- Lanes: {s['lane_count']} ({s['lanes_with_volume']} with volume)",
           f"- Countries: {', '.join(s['countries'])}",
           f"- Annual pallets (known): {s['annual_pallets_known']}",
           f"- Hazardous lanes: {s['hazardous_lanes']}",
           f"- Readiness: {sm['readiness_pct']}% of lanes have no gaps", "",
           "## Gaps"]
    for g in result["gaps"]:
        out.append(f"- [{g['severity']}] {g['rule_id']} {g['lane_id'] or 'requirements'}: {g['message']}")
    out += ["", "## Clarification questions"]
    for t in result["questions"]:
        out.append(f"### {t['theme']}")
        out += [f"{i}. {q}" for i, q in enumerate(t["questions"], 1)]
    out += ["", "## Solution outline"]
    for b in result["outline"]["bands"]:
        out.append(f"- {b['band']}: {b['lane_count']} lanes, {b['annual_pallets']} pallets a year. {b['rationale']}")
    out += [f"- Next: {x}" for x in result["outline"]["next_steps"]]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check an RFQ pack for gaps.")
    ap.add_argument("pack", type=Path, help="folder with lanes.csv and requirements.md")
    ap.add_argument("--markdown", action="store_true", help="print a readable report instead of JSON")
    args = ap.parse_args(argv)
    rows, req, meta = load_pack(args.pack)
    result = check(rows, req)
    sys.stdout.write(to_markdown(meta, result) if args.markdown else json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
