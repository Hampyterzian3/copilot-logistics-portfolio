"""Tests for rfq_checker: one block per rule, plus scope, outline, pack and parity checks."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rfq_checker as rc  # noqa: E402

COMPLETE_REQ = """# RFQ
## Contract period
Two years.
## Service levels
97% on time.
## Pricing format
Rate card.
## Fuel mechanism
Indexed.
## Liability and insurance
CMR.
## Invoicing and payment
60 days.
"""


def lane(**over) -> dict:
    base = {
        "lane_id": "T-001", "origin_country": "DE", "origin_city": "Stuttgart",
        "dest_country": "PL", "dest_city": "Poznan", "distance_km": "900",
        "mode_requested": "Road FTL", "annual_shipments": "104", "pallets_per_shipment": "26",
        "pallet_length_cm": "120", "pallet_width_cm": "80", "pallet_height_cm": "140",
        "weight_kg_per_pallet": "400", "incoterm": "DAP", "hazardous": "N", "un_number": "",
        "required_transit_days": "2",
    }
    base.update(over)
    return base


def rule_ids(rows, req=COMPLETE_REQ):
    return [g["rule_id"] for g in rc.check(rows, req)["gaps"]]


def test_clean_lane_has_no_gaps():
    res = rc.check([lane()], COMPLETE_REQ)
    assert res["gaps"] == []
    assert res["summary"]["readiness_pct"] == 100


# R01 missing annual volume
@pytest.mark.parametrize("field", ["annual_shipments", "pallets_per_shipment"])
@pytest.mark.parametrize("value", ["", "  ", "0", "n/a"])
def test_r01_missing_volume(field, value):
    res = rc.check([lane(**{field: value})], COMPLETE_REQ)
    assert [g["rule_id"] for g in res["gaps"]] == ["R01"]
    assert res["gaps"][0]["severity"] == "high"
    assert res["lanes"][0]["annual_pallets"] is None
    assert res["lanes"][0]["mode_suggested"] == "Pending data"


# R02 missing pallet dimensions
def test_r02_missing_dimensions_lists_each_field():
    g = rc.check([lane(pallet_length_cm="", pallet_height_cm="")], COMPLETE_REQ)["gaps"]
    assert [x["rule_id"] for x in g] == ["R02"]
    assert g[0]["field"] == "pallet_length_cm, pallet_height_cm"
    assert g[0]["severity"] == "medium"


# R03 unclear Incoterm
@pytest.mark.parametrize("value", ["", "TBC", "DDU", "EXW/FCA", "Free house"])
def test_r03_unclear_incoterm(value):
    assert rule_ids([lane(incoterm=value)]) == ["R03"]


@pytest.mark.parametrize("value", ["FCA Pilsen", "dap", "DDP", "CPT", "EXW", "DPU", "CIP"])
def test_r03_valid_incoterms_pass(value):
    assert rule_ids([lane(incoterm=value)]) == []


# R04 sea-only Incoterm on road lane
@pytest.mark.parametrize("value", ["FOB", "FOB Hamburg", "CIF", "CFR", "FAS"])
def test_r04_sea_only_incoterm(value):
    g = rc.check([lane(incoterm=value)], COMPLETE_REQ)["gaps"]
    assert [x["rule_id"] for x in g] == ["R04"]
    assert g[0]["severity"] == "low"


# R05 hazardous goods without UN number
@pytest.mark.parametrize("un", ["", "1263", "TBC", "UN12", "UN 1263"])
def test_r05_hazardous_without_valid_un(un):
    assert rule_ids([lane(hazardous="Y", un_number=un)]) == ["R05"]


def test_r05_valid_un_and_non_hazardous_pass():
    assert rule_ids([lane(hazardous="Y", un_number="UN3082")]) == []
    assert rule_ids([lane(hazardous="yes", un_number="un1866")]) == []
    assert rule_ids([lane(hazardous="N", un_number="")]) == []


# R06 unrealistic transit time
def test_r06_transit_below_road_minimum():
    g = rc.check([lane(distance_km="1950", required_transit_days="2")], COMPLETE_REQ)["gaps"]
    assert [x["rule_id"] for x in g] == ["R06"]
    assert "road minimum is about 3 day(s)" in g[0]["message"]


@pytest.mark.parametrize("km,days,flag", [(650, 1, False), (651, 1, True), (1300, 2, False), (100, 0, True)])
def test_r06_boundaries(km, days, flag):
    assert ("R06" in rule_ids([lane(distance_km=str(km), required_transit_days=str(days))])) is flag


# R07 duplicate lane
def test_r07_duplicate_lane_points_to_first():
    rows = [lane(), lane(lane_id="T-002", origin_city=" stuttgart ", annual_shipments="52"), lane(lane_id="T-003", dest_city="Vienna")]
    g = rc.check(rows, COMPLETE_REQ)["gaps"]
    assert [(x["rule_id"], x["lane_id"], x["detail"]) for x in g] == [("R07", "T-002", "T-001")]


# R08 missing requirements section
def test_r08_missing_sections():
    req = "# RFQ\n## Pricing format\nRate card.\n## Service levels and KPIs\n97%.\n"
    g = [x for x in rc.check([lane()], req)["gaps"] if x["rule_id"] == "R08"]
    assert [x["detail"] for x in g] == ["Contract period", "Fuel mechanism", "Liability and insurance", "Invoicing and payment"]
    assert all(x["lane_id"] is None for x in g)


# R09 open TBC items
def test_r09_open_items():
    req = COMPLETE_REQ + "- Monthly KPI report, format TBC.\n- Base month TBD\nTBCX is not an open item.\n"
    g = [x for x in rc.check([lane()], req)["gaps"] if x["rule_id"] == "R09"]
    assert [x["detail"] for x in g] == ["Monthly KPI report, format TBC.", "Base month TBD"]


# Mode bands
@pytest.mark.parametrize("km,ships,pps,band", [
    (900, 104, 26, "FTL"),
    (1200, 104, 26, "Multimodal (road-rail)"),
    (1200, 24, 26, "FTL"),
    (1200, 104, 12, "LTL/groupage"),
])
def test_mode_bands(km, ships, pps, band):
    res = rc.check([lane(distance_km=str(km), annual_shipments=str(ships), pallets_per_shipment=str(pps),
                         required_transit_days="5")], COMPLETE_REQ)
    assert res["lanes"][0]["mode_suggested"] == band


def test_questions_grouped_by_theme_in_order():
    rows = [lane(incoterm="TBC"), lane(lane_id="T-002", dest_city="Vienna", hazardous="Y"),
            lane(lane_id="T-003", dest_city="Lyon", annual_shipments="")]
    q = rc.check(rows, COMPLETE_REQ)["questions"]
    assert [t["theme"] for t in q] == ["Volumes and forecasts", "Dangerous goods", "Commercial terms"]
    assert "T-002" in q[1]["questions"][0]


# Seeded sample packs
def load(name):
    return rc.load_pack(ROOT / "data" / name)


def test_northwind_europe_pack_finds_every_seeded_gap():
    rows, req, meta = load("northwind-europe-2027")
    res = rc.check(rows, req)
    assert len(rows) == 40
    assert res["summary"]["gaps_by_rule"] == {"R01": 3, "R02": 4, "R03": 4, "R04": 2, "R05": 3,
                                              "R06": 3, "R07": 2, "R08": 2, "R09": 2}
    assert res["summary"]["gaps_by_severity"] == {"high": 9, "medium": 12, "low": 4}
    assert {b["band"]: b["lane_count"] for b in res["outline"]["bands"]}["Pending data"] == 3
    assert res["scope"]["lane_count"] == 40 and len(res["scope"]["countries"]) >= 10


def test_spares_pack_is_mostly_clean():
    rows, req, meta = load("northwind-spares-2027")
    res = rc.check(rows, req)
    assert [g["rule_id"] for g in res["gaps"]] == ["R02", "R05", "R09"]
    assert res["summary"]["readiness_pct"] == 88


def test_cli_markdown(capsys):
    assert rc.main([str(ROOT / "data" / "northwind-spares-2027"), "--markdown"]) == 0
    out = capsys.readouterr().out
    assert "## Clarification questions" in out and chr(0x2014) not in out


# Python and JavaScript ports must agree on every sample pack
@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_port_matches_python():
    proc = subprocess.run(["node", str(ROOT / "src" / "check_parity.js")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PARITY OK" in proc.stdout
