"""Generate the synthetic RFQ packs for Tender Desk Copilot.

Fictional shipper: Northwind Components. Fictional operator: Contoso Logistics.
Seeded and reproducible: running this twice produces identical files.

Each pack is a folder under data/<pack-id>/ with:
  pack.json        metadata (id, title, shipper)
  lanes.csv        lane spreadsheet as the shipper would send it
  requirements.md  the tender requirements document

Gaps are seeded deliberately at fixed positions so tests can assert them.
"""
from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

CITIES = {
    "Stuttgart": ("DE", 48.78, 9.18), "Pilsen": ("CZ", 49.75, 13.38),
    "Wroclaw": ("PL", 51.11, 17.03), "Gyor": ("HU", 47.69, 17.63),
    "Rotterdam": ("NL", 51.92, 4.48), "Lyon": ("FR", 45.76, 4.84),
    "Milan": ("IT", 45.46, 9.19), "Barcelona": ("ES", 41.39, 2.17),
    "Valencia": ("ES", 39.47, -0.38), "Gothenburg": ("SE", 57.71, 11.97),
    "Antwerp": ("BE", 51.22, 4.40), "Vienna": ("AT", 48.21, 16.37),
    "Bratislava": ("SK", 48.15, 17.11), "Cluj": ("RO", 46.77, 23.59),
    "Turin": ("IT", 45.07, 7.69), "Poznan": ("PL", 52.41, 16.93),
    "Munich": ("DE", 48.14, 11.58), "Hamburg": ("DE", 53.55, 9.99),
    "Ghent": ("BE", 51.05, 3.72), "Porto": ("PT", 41.15, -8.61),
    "Seville": ("ES", 37.39, -5.98), "Bucharest": ("RO", 44.43, 26.10),
    "Kosice": ("SK", 48.72, 21.26), "Bordeaux": ("FR", 44.84, -0.58),
    "Lille": ("FR", 50.63, 3.06), "Bologna": ("IT", 44.49, 11.34),
}

COLUMNS = [
    "lane_id", "origin_country", "origin_city", "dest_country", "dest_city",
    "distance_km", "mode_requested", "annual_shipments", "pallets_per_shipment",
    "pallet_length_cm", "pallet_width_cm", "pallet_height_cm", "weight_kg_per_pallet",
    "incoterm", "hazardous", "un_number", "required_transit_days",
]

ROAD_KM_PER_DAY = 650  # must match rfq_checker.ROAD_KM_PER_DAY
UN_NUMBERS = ["UN1263", "UN1866", "UN3082", "UN2794", "UN3480"]


def road_km(a: str, b: str) -> int:
    """Great-circle distance times a 1.25 road factor, rounded to 10 km."""
    _, la1, lo1 = CITIES[a]
    _, la2, lo2 = CITIES[b]
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    km = 2 * 6371 * math.asin(math.sqrt(h)) * 1.25
    return int(round(km / 10.0)) * 10


def min_days(km: int) -> int:
    return max(1, -(-km // ROAD_KM_PER_DAY))


def clean_lane(rng: random.Random, origin: str, dest: str, profile: str) -> dict:
    km = road_km(origin, dest)
    if profile == "full":
        pps = rng.randint(22, 33)
    elif profile == "mid":
        pps = rng.randint(10, 21)
    else:
        pps = rng.randint(2, 9)
    hazardous = rng.random() < 0.15
    width = rng.choice([80, 80, 80, 100])
    return {
        "origin_country": CITIES[origin][0], "origin_city": origin,
        "dest_country": CITIES[dest][0], "dest_city": dest,
        "distance_km": str(km),
        "mode_requested": "Road FTL" if pps >= 22 else rng.choice(["Road LTL", "Any"]),
        "annual_shipments": str(rng.choice([12, 24, 48, 52, 78, 104, 156, 208, 260])),
        "pallets_per_shipment": str(pps),
        "pallet_length_cm": "120", "pallet_width_cm": str(width),
        "pallet_height_cm": str(rng.choice([100, 110, 120, 140, 160])),
        "weight_kg_per_pallet": str(rng.randrange(250, 701, 10)),
        "incoterm": rng.choice(["FCA", "DAP", "DAP", "DDP", "CPT", "EXW"]),
        "hazardous": "Y" if hazardous else "N",
        "un_number": rng.choice(UN_NUMBERS) if hazardous else "",
        "required_transit_days": str(min_days(km) + rng.randint(0, 2)),
    }


def build_lanes(seed: int, origins: list[str], n_unique: int, profiles: list[str]) -> list[dict]:
    rng = random.Random(seed)
    dests = [c for c in CITIES if c not in origins]
    pairs = [(o, d) for o in origins for d in dests]
    rng.shuffle(pairs)
    lanes = [clean_lane(rng, o, d, rng.choice(profiles)) for o, d in pairs[:n_unique]]
    return lanes


def set_hazardous(lane: dict, un: str) -> None:
    lane["hazardous"] = "Y"
    lane["un_number"] = un


def inbound_pack() -> tuple[list[dict], dict]:
    """Main RFQ: 38 unique lanes plus 2 duplicates = 40 rows, many seeded gaps."""
    lanes = build_lanes(2027, ["Stuttgart", "Pilsen", "Wroclaw", "Gyor"], 38,
                        ["full", "full", "mid", "small"])
    # Seeded gaps (positions are 0-based in the 38 unique lanes, before duplicates are inserted)
    lanes[3]["annual_shipments"] = ""                      # R01
    lanes[11]["pallets_per_shipment"] = ""                 # R01
    lanes[24]["annual_shipments"] = ""                     # R01
    lanes[24]["pallets_per_shipment"] = ""
    lanes[6]["pallet_height_cm"] = ""                      # R02
    lanes[15]["pallet_length_cm"] = ""                     # R02
    lanes[15]["pallet_width_cm"] = ""
    lanes[29]["pallet_height_cm"] = ""                     # R02
    lanes[33].update(pallet_length_cm="", pallet_width_cm="", pallet_height_cm="")  # R02
    lanes[8]["incoterm"] = "TBC"                           # R03
    lanes[17]["incoterm"] = "DDU"                          # R03 (withdrawn rule)
    lanes[21]["incoterm"] = "EXW/FCA"                      # R03
    lanes[27]["incoterm"] = ""                             # R03
    lanes[31]["incoterm"] = "FOB Hamburg"                  # R04
    lanes[36]["incoterm"] = "CIF"                          # R04
    set_hazardous(lanes[5], "")                            # R05
    set_hazardous(lanes[19], "1263")                       # R05 (no UN prefix)
    set_hazardous(lanes[34], "TBC")                        # R05
    # R06: the three longest lanes get a transit time below the road minimum
    longest = sorted(range(len(lanes)), key=lambda i: (-int(lanes[i]["distance_km"]), i))[:3]
    for i in longest:
        lanes[i]["required_transit_days"] = str(max(1, min_days(int(lanes[i]["distance_km"])) - 2))
    # R07: two duplicates of existing corridors, inserted mid-file as a shipper would
    dup_a = dict(lanes[4], annual_shipments="52", mode_requested="Any")
    dup_b = dict(lanes[13], pallets_per_shipment="12", mode_requested="Road LTL")
    lanes.insert(20, dup_a)
    lanes.append(dup_b)
    for i, lane in enumerate(lanes, start=1):
        lane["lane_id"] = f"NW-{i:03d}"
    meta = {"id": "northwind-europe-2027", "shipper": "Northwind Components",
            "title": "European road network 2027",
            "received": "2026-10-12", "response_due": "2026-11-06"}
    return lanes, meta


def spares_pack() -> tuple[list[dict], dict]:
    """Second RFQ: 18 aftermarket spares lanes, mostly part loads, few gaps."""
    lanes = build_lanes(3101, ["Poznan", "Bologna"], 18, ["small", "small", "mid"])
    for lane in lanes:
        if lane["hazardous"] == "Y":  # keep spares non-hazardous except the seeded one
            lane["hazardous"], lane["un_number"] = "N", ""
    lanes[7]["pallet_height_cm"] = ""                      # R02
    set_hazardous(lanes[12], "")                           # R05
    for i, lane in enumerate(lanes, start=1):
        lane["lane_id"] = f"SP-{i:03d}"
    meta = {"id": "northwind-spares-2027", "shipper": "Northwind Components",
            "title": "Aftermarket spares distribution 2027",
            "received": "2026-10-15", "response_due": "2026-11-13"}
    return lanes, meta


INBOUND_REQ = """# Northwind Components: European road network 2027

## Scope
Northwind Components invites tenders for road transport between its four European plants and its customer and port locations listed in lanes.csv. Volumes are 2026 actuals unless stated.

## Contract period
Three years from 1 April 2027, with an annual rate review.

## Service levels and KPIs
- On-time delivery of 97% or better, measured against the agreed delivery window.
- Track and trace events for collection, departure and delivery.
- Monthly KPI report, format TBC.

## Pricing format
Rate card per lane in EUR per shipment and EUR per pallet. Use the lane IDs in lanes.csv.

## Dangerous goods
Some flows carry ADR goods. Carriers must hold valid ADR certification.

## Liability and insurance
CMR liability as a minimum. Additional cargo insurance requirement TBC.

## Submission
Return the completed rate card and a solution description by the response date.
"""

SPARES_REQ = """# Northwind Components: Aftermarket spares distribution 2027

## Scope
Distribution of aftermarket spare parts from two regional warehouses to dealers and service centres listed in lanes.csv.

## Contract period
Two years from 1 May 2027.

## Service levels and KPIs
- Next-day or two-day delivery as stated per lane.
- Proof of delivery within 24 hours.

## Pricing format
Rate card per lane, EUR per pallet, with a minimum charge per shipment.

## Fuel mechanism
Monthly fuel surcharge indexed to the published diesel price, base month TBC.

## Liability and insurance
CMR liability as a minimum.

## Invoicing and payment
Monthly consolidated invoice, payment 60 days from invoice date.
"""


def write_pack(lanes: list[dict], meta: dict, req: str) -> None:
    folder = DATA / meta["id"]
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "lanes.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({k: lane[k] for k in COLUMNS} for lane in lanes)
    (folder / "requirements.md").write_text(req, encoding="utf-8", newline="\n")
    (folder / "pack.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    lanes, meta = inbound_pack()
    write_pack(lanes, meta, INBOUND_REQ)
    lanes, meta = spares_pack()
    write_pack(lanes, meta, SPARES_REQ)
    print(f"Wrote packs to {DATA}")


if __name__ == "__main__":
    main()
