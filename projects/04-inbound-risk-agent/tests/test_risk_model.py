import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

import generate_data as gen  # noqa: E402
import risk_model as rm  # noqa: E402
from alert_card import build_alert_card  # noqa: E402

BASE = {
    "shipment_id": "T1", "customer": "Adventure Works", "carrier": "Fabrikam Freight", "lane": "PL-POZ > NL",
    "area": "NL-Z01", "dest_country": "NL", "last_scan_label": "pickup", "last_scan_location": "Poznan hub",
    "lane_delay_rate": 0.05, "area_loss_rate": 0.002, "network_loss_rate": 0.006, "carrier_on_time": 0.96,
    "dwell_hours": 5.0, "dwell_norm_hours": 10.0, "customs_status": "not_required",
    "days_to_promise": 3.0, "remaining_transit_days": 1.0, "non_working_days": 0, "holiday_name": "",
}


@pytest.fixture(scope="module")
def data():
    return gen.generate()


@pytest.fixture(scope="module")
def rates(data):
    return rm.compute_rates(data["history"])


def test_weights_sum_to_100():
    assert sum(w for _, w in rm.WEIGHTS) == 100


def test_clean_shipment_scores_zero_and_on_track():
    r = rm.score_shipment(BASE)
    assert r["score"] == 0 and r["band"] == "on_track" and r["reasons"] == []


def test_worst_case_scores_100_and_critical():
    f = {**BASE, "lane_delay_rate": 0.5, "area_loss_rate": 0.05, "carrier_on_time": 0.6, "dwell_hours": 50.0,
         "customs_status": "held", "days_to_promise": -2.0, "non_working_days": 2, "holiday_name": "Armistice Day"}
    r = rm.score_shipment(f)
    assert r["score"] == 100 and r["band"] == "critical"
    assert len(r["reasons"]) == rm.MAX_REASONS


@pytest.mark.parametrize("score,band", [(0, "on_track"), (24, "on_track"), (25, "watch"), (39, "watch"),
                                        (40, "at_risk"), (54, "at_risk"), (55, "critical"), (100, "critical")])
def test_band_thresholds(score, band):
    assert rm.band_for(score) == band


@pytest.mark.parametrize("key,worse", [("lane_delay_rate", 0.25), ("area_loss_rate", 0.03), ("carrier_on_time", 0.80),
                                       ("dwell_hours", 30.0), ("days_to_promise", 0.5), ("non_working_days", 2)])
def test_each_factor_raises_score(key, worse):
    assert rm.score_shipment({**BASE, key: worse})["score"] > rm.score_shipment(BASE)["score"]


def test_reasons_are_ranked_plain_words():
    f = {**BASE, "dwell_hours": 40.0, "customs_status": "held", "area_loss_rate": 0.039}
    r = rm.score_shipment(f)
    pts = [x["points"] for x in r["reasons"]]
    assert pts == sorted(pts, reverse=True)
    assert r["reasons"][0]["text"] == "No scan for 40 h since the pickup scan at Poznan hub, 4.0x the usual 10 h"
    assert any(x["text"] == "Held by customs, not yet released" for x in r["reasons"])
    assert "BE" not in r["reasons"][1]["text"] and "NL-Z01 lost 3.9%" in r["reasons"][1]["text"]


def test_overdue_and_holiday_wording():
    f = {**BASE, "days_to_promise": -1.25, "non_working_days": 1, "holiday_name": "Armistice Day"}
    texts = [x["text"] for x in rm.score_shipment(f)["reasons"]]
    assert "Already 1.3 days past the promised date, about 1.0 days of transit left" in texts
    assert "1 non-working day before the promised date, including Armistice Day" in texts


def test_generator_is_reproducible():
    a, b = gen.generate(7), gen.generate(7)
    assert [s["shipment_id"] for s in a["in_transit"]] == [s["shipment_id"] for s in b["in_transit"]]
    assert [s["dwell_hours"] for s in a["history"][:50]] == [s["dwell_hours"] for s in b["history"][:50]]


def test_volumes(data):
    assert len(data["in_transit"]) == gen.N_IN_TRANSIT == 300
    assert len({s["shipment_id"] for s in data["in_transit"]}) == 300
    assert {e["shipment_id"] for e in data["scan_events"]} == {s["shipment_id"] for s in data["in_transit"]}


def test_two_seeded_high_risk_areas_are_found_from_history(rates):
    ranked = sorted(rates["area_loss_rate"], key=rates["area_loss_rate"].get, reverse=True)
    assert set(ranked[:2]) == set(gen.HIGH_RISK_AREAS)
    third = rates["area_loss_rate"][ranked[2]]
    assert min(rates["area_loss_rate"][a] for a in ranked[:2]) > 3 * third


def test_live_scores_in_range_with_every_band(data, rates):
    scored = [rm.score_shipment(rm.build_features(s, rates)) for s in data["in_transit"]]
    assert all(0 <= s["score"] <= 100 for s in scored)
    assert {s["band"] for s in scored} == {"critical", "at_risk", "watch", "on_track"}


def test_confusion_counts():
    c = rm.confusion([True, True, False, False, True], [True, False, True, False, True])
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (2, 1, 1, 1)
    assert c["precision"] == round(2 / 3, 4) and c["recall"] == round(2 / 3, 4)


def test_backtest_is_out_of_time_and_consistent(data):
    cutoff = datetime(2026, 8, 1)
    bt = rm.backtest(data["history"], cutoff)
    assert bt["train_snapshots"] + bt["test_snapshots"] == len(data["history"])
    c = bt["critical"]
    assert c["tp"] + c["fn"] == bt["test_late"]
    assert c["tp"] + c["fp"] + c["fn"] + c["tn"] == bt["test_snapshots"]
    # banding must separate outcomes: late rate falls band by band
    rates_by_band = [bt["by_band"][b]["late_rate"] for b in ("critical", "at_risk", "watch", "on_track")]
    assert rates_by_band == sorted(rates_by_band, reverse=True)
    assert c["precision"] > bt["test_late_rate"] * 3
    assert bt["watch_or_above"]["recall"] >= bt["at_risk_or_above"]["recall"] >= c["recall"]


def test_alert_card_is_adaptive_card_1_5(data, rates):
    rec = rm.build_features(data["in_transit"][0], rates)
    rec.update({"po_ref": "PO-1", "promised_display": "Tue 10 Nov 2026, 17:00"})
    card = build_alert_card(rec, rm.score_shipment(rec))
    assert card["type"] == "AdaptiveCard" and card["version"] == "1.5"
    assert card["$schema"].startswith("http://adaptivecards.io/schemas/")
    assert [a["title"] for a in card["actions"]] == ["Acknowledge", "Draft customer update", "Escalate to carrier"]
    assert all(a["type"] == "Action.Submit" and a["data"]["shipmentId"] == rec["shipment_id"] for a in card["actions"])


def test_exported_card_file_valid():
    card = json.loads((PROJECT / "teams" / "alert-card.json").read_text(encoding="utf-8"))
    allowed = {"Container", "TextBlock", "FactSet"}
    assert card["version"] == "1.5" and all(el["type"] in allowed for el in card["body"])
    assert card["body"][0]["items"][0]["text"].startswith("Critical inbound risk")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_port_matches_python_export():
    out = subprocess.run(["node", str(PROJECT / "src" / "verify_js_parity.js")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "mismatches: 0" in out.stdout
