import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import briefing as b  # noqa: E402

ROWS = b.generate_dataset()
WEEKS = range(b.BASELINE_WEEKS, b.N_WEEKS)


@pytest.fixture(scope="module")
def built():
    return {i: b.build_week(ROWS, i) for i in WEEKS}


# ---------------------------------------------------------------- dataset
def test_dataset_shape_and_reproducible():
    assert len(ROWS) == 6 * 26
    assert b.generate_dataset() == ROWS
    assert len({r["customer"] for r in ROWS}) == 6
    for r in ROWS:
        assert r["revenue"] > r["cost"] > 0
        assert 0 < r["otp_pct"] <= 100


def test_portfolio_ratios_recomputed_from_sums():
    p = b.portfolio_rows(ROWS)[10]
    wk = [r for r in ROWS if r["week_index"] == 10]
    rev, cost = sum(r["revenue"] for r in wk), sum(r["cost"] for r in wk)
    assert p["margin_pct"] == pytest.approx((rev - cost) / rev * 100, abs=0.01)


# ---------------------------------------------------------------- variance engine
def test_variance_maths():
    s = [100, 100, 100, 100, 100, 100, 100, 100, 130]
    v = b.variance(s, 8, "shipments")
    assert v["baseline"] == 100 and v["vs_base"] == pytest.approx(0.30) and v["wow"] == pytest.approx(0.30)
    assert v["flagged"] and v["favourable"]


def test_needs_full_baseline():
    with pytest.raises(ValueError):
        b.compute_variances(ROWS, b.BASELINE_WEEKS - 1)


@pytest.mark.parametrize("event", b.EVENTS, ids=lambda e: e["type"])
def test_seeded_events_are_detected_and_ranked_first(event):
    metric = {"margin_dip": "margin_pct", "otp_drop": "otp_pct", "volume_surge": "shipments"}[event["type"]]
    for i in event["weeks"]:
        ranked = b.rank_materiality(b.compute_variances(ROWS, i))
        hits = [v for v in ranked if v["customer_id"] == event["customer"] and v["metric"] == metric]
        assert hits and hits[0]["tag"] == "High", (event["type"], i)
        assert ranked[0]["customer_id"] == event["customer"], (event["type"], i)


def test_no_flags_in_quiet_weeks_are_high():
    event_weeks = {i for e in b.EVENTS for i in e["weeks"]}
    for i in WEEKS:
        if i in event_weeks:
            continue
        assert all(v["tag"] != "High" for v in b.rank_materiality(b.compute_variances(ROWS, i))), i


# ---------------------------------------------------------------- materiality ranking
def test_ranking_is_sorted_and_flagged_only():
    for i in WEEKS:
        ranked = b.rank_materiality(b.compute_variances(ROWS, i))
        assert all(v["flagged"] for v in ranked)
        scores = [v["score"] for v in ranked]
        assert scores == sorted(scores, reverse=True)


def test_materiality_scales_with_z_weight_and_size():
    avg = 1 / 6
    assert b.materiality_score(4, "margin_pct", avg) > b.materiality_score(2, "margin_pct", avg)
    assert b.materiality_score(3, "margin_pct", avg) > b.materiality_score(3, "co2", avg)
    assert b.materiality_score(3, "otp_pct", 0.30) > b.materiality_score(3, "otp_pct", 0.10)
    assert b.materiality_score(-3, "otp_pct", avg) == b.materiality_score(3, "otp_pct", avg)
    assert b.materiality_score(50, "revenue", avg) == b.materiality_score(8, "revenue", avg)  # capped


def test_tags():
    assert b.materiality_tag(b.TAG_HIGH) == "High"
    assert b.materiality_tag(b.TAG_MEDIUM) == "Medium"
    assert b.materiality_tag(b.TAG_MEDIUM - 0.01) == "Low"


def test_ranking_tie_break_prefers_larger_customer():
    a = {"flagged": True, "score": 5.0, "revenue_share": 0.1, "customer": "A", "metric": "revenue"}
    c = {"flagged": True, "score": 5.0, "revenue_share": 0.3, "customer": "C", "metric": "revenue"}
    x = {"flagged": False, "score": 9.0, "revenue_share": 0.3, "customer": "X", "metric": "revenue"}
    assert [v["customer"] for v in b.rank_materiality([a, x, c])] == ["C", "A"]


# ---------------------------------------------------------------- no claim without data
def _all_sentences(w):
    br = w["brief"]
    return [br["headline"], br["summary"], *br["things"], *br["callouts"], *br["actions"],
            *[x for s in w["slides"] for x in s["bullets"]], *w["teams"]["lines"]]


def test_every_sentence_has_valid_refs_and_supported_numbers(built):
    for i, w in built.items():
        book = b.FactBook(w["week"])
        book.facts = w["facts"]
        assert b.validate_sentences(_all_sentences(w), book) == [], w["week"]


def test_validator_rejects_unsupported_claims(built):
    w = built[b.N_WEEKS - 1]
    book = b.FactBook(w["week"])
    book.facts = w["facts"]
    fid = w["brief"]["headline"]["refs"][0]
    assert b.validate_sentences([b.S("Margin fell 9.9 pp.", fid)], book)        # number not in fact
    assert b.validate_sentences([b.S("Revenue is strong.")], book)              # no ref at all
    assert b.validate_sentences([b.S("Revenue is strong.", "F999")], book)      # unknown ref


def test_facts_match_dataset(built):
    w = built[b.N_WEEKS - 1]
    row = next(r for r in ROWS if r["customer_id"] == "NWA" and r["week_index"] == b.N_WEEKS - 1)
    f = w["facts"][w["customer_facts"]["NWA"]["shipments"]]
    assert f["value"] == row["shipments"] and f["value_fmt"] == f"{row['shipments']:,}"


def test_brief_structure(built):
    for w in built.values():
        assert 1 <= len(w["brief"]["things"]) <= 3
        assert len(w["brief"]["callouts"]) == 6
        assert len(w["slides"]) == 5
        assert 1 <= len(w["brief"]["actions"]) <= 4
        text = " ".join(s["text"] for s in _all_sentences(w))
        assert chr(0x2014) not in text  # no em dashes


def test_margin_bridge_adds_up():
    for cid, *_ in b.CUSTOMERS:
        br = b.margin_bridge(ROWS, cid, 18)
        assert br["rate_effect"] + br["cost_effect"] == pytest.approx(br["margin_now"] - br["margin_base"])
    fbs = b.margin_bridge(ROWS, "FBS", 18)
    assert fbs["cost_effect"] < -3 and abs(fbs["rate_effect"]) < 1  # seeded dip is a cost problem
