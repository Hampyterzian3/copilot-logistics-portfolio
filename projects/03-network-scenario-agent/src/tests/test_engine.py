import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from network_engine import MODES, evaluate, generate, haversine_km, params_with, road_km, run_scenario  # noqa: E402
from network_engine.api import ValidationError, handle_scenario  # noqa: E402
from network_engine.model import build_routes  # noqa: E402


@pytest.fixture(scope="module")
def net():
    return generate()


def test_haversine_known_distances():
    # Frankfurt to Munich is about 304 km great-circle
    assert haversine_km(50.1109, 8.6821, 48.1351, 11.5820) == pytest.approx(304, abs=3)
    # Quarter of the meridian: equator to pole
    assert haversine_km(0, 0, 90, 0) == pytest.approx(math.pi * 6371 / 2, rel=1e-9)
    assert haversine_km(48.0, 2.0, 48.0, 2.0) == 0.0


def test_road_factor_applied():
    p = params_with({"road_factor": 1.3})
    a, b = {"lat": 50.0, "lon": 8.0}, {"lat": 51.0, "lon": 9.0}
    assert road_km(a, b, p) == pytest.approx(1.3 * haversine_km(50, 8, 51, 9))


def test_generator_is_reproducible(net):
    assert len(net["suppliers"]) == 60
    assert generate() == net
    assert len(net["hubs"]) == 3


@pytest.mark.parametrize("stops", [1, 2, 4, 6])
def test_milkrun_capacity_and_stops_respected(net, stops):
    p = params_with({"max_stops": stops})
    members = [(s, s["ldm_week"] / 5 % p["capacity_ldm"]) for s in net["suppliers"] if s["region"] == "DE-S"]
    routes = build_routes(members, net["plant"], p)
    assert sorted(s["id"] for r in routes for s, _ in r) == sorted(s["id"] for s, _ in members)
    for r in routes:
        assert len(r) <= stops
        assert sum(load for _, load in r) <= p["capacity_ldm"] + 1e-9


@pytest.mark.parametrize("mode", MODES)
def test_every_milkrun_and_collection_flow_within_capacity(net, mode):
    p = params_with({})
    res = evaluate(net["suppliers"], net["plant"], net["hubs"], {s["id"]: mode for s in net["suppliers"]}, p)
    assert res["cost_week"] > 0 and res["co2_t_week"] > 0 and res["trucks_week"] > 0
    allocated = sum(a["cost"] for a in res["alloc"].values())
    assert allocated == pytest.approx(res["cost_week"], rel=1e-9)


def test_direct_trucks_cover_volume(net):
    p = params_with({})
    s = max(net["suppliers"], key=lambda x: x["ldm_week"])
    res = evaluate([s], net["plant"], net["hubs"], {s["id"]: "direct"}, p)
    assert res["trucks_week"] * p["capacity_ldm"] >= s["ldm_week"]


@pytest.mark.parametrize("overrides", [
    {}, {"fuel_index": 1.5}, {"handling_ldm": 2}, {"max_stops": 2}, {"max_stops": 7},
])
def test_best_mix_never_worse_than_any_pure_design(net, overrides):
    res = run_scenario(net, overrides)
    mix = res["designs"]["bestmix"]["cost_week"]
    for m in MODES:
        assert mix <= res["designs"][m]["cost_week"] + 1e-6


@pytest.mark.parametrize("price", [50, 150, 300])
def test_co2_priced_mix_beats_cost_only_mix_at_that_price(net, price):
    low = run_scenario(net, {"co2_price_t": 0})["designs"]["bestmix"]
    res = run_scenario(net, {"co2_price_t": price})
    high = res["designs"]["bestmix"]
    assert high["objective"] <= low["cost_week"] + price * low["co2_t_week"] + 1e-6
    for m in MODES:
        assert high["objective"] <= res["designs"][m]["objective"] + 1e-6


def test_fuel_index_raises_cost(net):
    base = run_scenario(net)["designs"]["direct"]["cost_week"]
    dear = run_scenario(net, {"fuel_index": 1.5})["designs"]["direct"]["cost_week"]
    assert dear > base


def test_api_contract(net):
    out = handle_scenario({"fuel_index": 1.2, "co2_price_t": 80, "hubs": ["HUB-IT", "HUB-CZ"]}, net)
    assert set(out["designs"]) == {"direct", "milkrun", "crossdock", "bestmix"}
    assert out["recommendation"]["saving_vs_best_pure_eur_week"] >= 0
    assert all(m["hub_id"] in (None, "HUB-IT", "HUB-CZ") for m in out["supplier_modes"])
    json.dumps(out)
    with pytest.raises(ValidationError):
        handle_scenario({"fuel_index": 9})
    with pytest.raises(ValidationError):
        handle_scenario({"hubs": ["HUB-XX"]})


def test_baseline_export_matches_engine(net):
    path = Path(__file__).resolve().parents[4] / "site" / "demos" / "data" / "03-baseline.json"
    if not path.exists():
        pytest.skip("run python -m network_engine.export first")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["network"] == net
    base = run_scenario(net)
    for d, r in data["scenarios"][0]["results"].items():
        assert r["cost_week"] == pytest.approx(base["designs"][d]["cost_week"], abs=0.01)
