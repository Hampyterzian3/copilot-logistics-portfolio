"""Inbound network cost, CO2 and vehicle-movement model.

Pure Python, no third-party dependencies. The same logic is ported 1:1 to
JavaScript in site/demos/03-network-scenario-agent.html (between the
ENGINE START / ENGINE END markers), so keep the two in step.

Designs
- direct:    every supplier ships full or part loads straight to the plant.
- milkrun:   suppliers grouped by region, collected by daily milk-runs
             (nearest-neighbour routes with capacity and stop limits).
- crossdock: suppliers collected by daily milk-runs into the nearest
             candidate hub, then consolidated line-haul hub to plant.
- bestmix:   per supplier the mode that minimises cost + CO2 price, found by
             allocation seeding and single-supplier improvement moves.
             Never worse than the best pure design.
"""
from __future__ import annotations

import math

MODES = ("direct", "milkrun", "crossdock")
EARTH_RADIUS_KM = 6371.0

DEFAULT_PARAMS = {
    "capacity_ldm": 13.6,        # loading metres per trailer
    "road_factor": 1.2,          # road km per great-circle km
    "runs_per_week": 5,          # milk-run and line-haul days per week
    "max_stops": 4,              # pick-up stops per milk-run
    "ftl_rate_km": 1.55,         # EUR per km, full truck / milk-run
    "linehaul_rate_km": 1.35,    # EUR per km, contracted hub line-haul
    "fuel_share": 0.30,          # share of the km rate driven by diesel
    "fuel_index": 1.0,           # 1.0 = base diesel price
    "trip_fixed": 90.0,          # EUR per trip (dock slot, admin)
    "stop_cost": 35.0,           # EUR per milk-run pick-up stop
    "handling_ldm": 6.0,         # EUR per loading metre cross-docked
    "co2_vkm": 0.60,             # kg CO2 per vehicle km (empty truck)
    "co2_tkm": 0.0125,           # kg CO2 per additional tonne km
    "co2_price_t": 0.0,          # EUR per tonne CO2 (shadow price)
}


def params_with(overrides: dict | None = None) -> dict:
    p = dict(DEFAULT_PARAMS)
    for k, v in (overrides or {}).items():
        if k not in p:
            raise KeyError(f"unknown parameter: {k}")
        p[k] = float(v) if k not in ("runs_per_week", "max_stops") else int(v)
    return p


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def road_km(a: dict, b: dict, p: dict) -> float:
    return haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) * p["road_factor"]


def fuel_factor(p: dict) -> float:
    return (1 - p["fuel_share"]) + p["fuel_share"] * p["fuel_index"]


def trip_cost(km: float, p: dict, rate_key: str = "ftl_rate_km") -> float:
    return p["trip_fixed"] + km * p[rate_key] * fuel_factor(p)


def trip_co2_kg(km: float, tonnes: float, p: dict) -> float:
    return km * p["co2_vkm"] + km * tonnes * p["co2_tkm"]


def _new_alloc():
    return {"cost": 0.0, "co2_kg": 0.0}


def _direct(s, plant, p, alloc, flows, totals):
    """Supplier ships its weekly volume in `freq` shipments, full trucks."""
    cap = p["capacity_ldm"]
    load = s["ldm_week"] / s["freq"]
    trucks = math.ceil(load / cap - 1e-9)
    trips = s["freq"] * trucks
    km = road_km(s, plant, p)
    tonnes = load / trucks * s["t_per_ldm"]
    cost = trips * trip_cost(km, p)
    co2 = trips * trip_co2_kg(km, tonnes, p)
    alloc[s["id"]]["cost"] += cost
    alloc[s["id"]]["co2_kg"] += co2
    totals["cost"] += cost
    totals["co2_kg"] += co2
    totals["trips"] += trips
    totals["arrivals"] += trips
    totals["vkm"] += trips * km
    flows.append({"kind": "direct", "path": [s["id"], "PLANT"], "trips": trips})


def _full_truck_split(s, p):
    """Daily volume above whole trailers goes direct; remainder is pooled."""
    cap = p["capacity_ldm"]
    daily = s["ldm_week"] / p["runs_per_week"]
    full = math.floor(daily / cap + 1e-9)
    rest = daily - full * cap
    if rest < 1e-6:
        rest = 0.0
    return full, rest


def _full_trucks(s, full, plant, p, alloc, flows, totals):
    if full <= 0:
        return
    trips = full * p["runs_per_week"]
    km = road_km(s, plant, p)
    tonnes = p["capacity_ldm"] * s["t_per_ldm"]
    cost = trips * trip_cost(km, p)
    co2 = trips * trip_co2_kg(km, tonnes, p)
    alloc[s["id"]]["cost"] += cost
    alloc[s["id"]]["co2_kg"] += co2
    totals["cost"] += cost
    totals["co2_kg"] += co2
    totals["trips"] += trips
    totals["arrivals"] += trips
    totals["vkm"] += trips * km
    flows.append({"kind": "full", "path": [s["id"], "PLANT"], "trips": trips})


def build_routes(members: list, end: dict, p: dict) -> list:
    """Nearest-neighbour milk-runs. members: list of (supplier, load_ldm).

    Start each route at the unassigned supplier furthest from `end`, then add
    the nearest supplier that still fits capacity, until max_stops.
    """
    cap = p["capacity_ldm"]
    pool = sorted(members, key=lambda m: (-road_km(m[0], end, p), m[0]["id"]))
    routes = []
    while pool:
        first = pool.pop(0)
        route = [first]
        load = first[1]
        cur = first[0]
        while len(route) < p["max_stops"]:
            best_i, best_d = -1, 0.0
            for i, m in enumerate(pool):
                if load + m[1] > cap + 1e-9:
                    continue
                d = road_km(cur, m[0], p)
                if best_i < 0 or d < best_d - 1e-9 or (abs(d - best_d) <= 1e-9 and m[0]["id"] < pool[best_i][0]["id"]):
                    best_i, best_d = i, d
            if best_i < 0:
                break
            m = pool.pop(best_i)
            route.append(m)
            load += m[1]
            cur = m[0]
        routes.append(route)
    return routes


def _run_routes(routes, end, end_id, p, alloc, flows, totals, to_plant):
    runs = p["runs_per_week"]
    for route in routes:
        km = 0.0
        tkm = 0.0
        tonnes = 0.0
        for i, (s, load) in enumerate(route):
            tonnes += load * s["t_per_ldm"]
            nxt = route[i + 1][0] if i + 1 < len(route) else end
            leg = road_km(s, nxt, p)
            km += leg
            tkm += leg * tonnes
        cost_run = p["trip_fixed"] + km * p["ftl_rate_km"] * fuel_factor(p) + len(route) * p["stop_cost"]
        co2_run = km * p["co2_vkm"] + tkm * p["co2_tkm"]
        cost, co2 = cost_run * runs, co2_run * runs
        weights = [load * road_km(s, end, p) + 1e-9 for s, load in route]
        wsum = sum(weights)
        for (s, _), w in zip(route, weights):
            alloc[s["id"]]["cost"] += cost * w / wsum
            alloc[s["id"]]["co2_kg"] += co2 * w / wsum
        totals["cost"] += cost
        totals["co2_kg"] += co2
        totals["trips"] += runs
        totals["vkm"] += runs * km
        if to_plant:
            totals["arrivals"] += runs
        flows.append({"kind": "milkrun" if to_plant else "collect",
                      "path": [s["id"] for s, _ in route] + [end_id], "trips": runs})


def nearest_hub(s, hubs, plant, p):
    return min(hubs, key=lambda h: (road_km(s, h, p) + road_km(h, plant, p), h["id"]))


def evaluate(suppliers: list, plant: dict, hubs: list, assign: dict, p: dict) -> dict:
    """Cost, CO2 and vehicle movements per week for a mode assignment."""
    totals = {"cost": 0.0, "co2_kg": 0.0, "trips": 0, "arrivals": 0, "vkm": 0.0, "handling": 0.0}
    alloc = {s["id"]: _new_alloc() for s in suppliers}
    flows = []
    by_region: dict = {}
    by_hub: dict = {}
    hub_of = {}
    for s in suppliers:
        mode = assign[s["id"]]
        if mode == "direct":
            _direct(s, plant, p, alloc, flows, totals)
            continue
        full, rest = _full_truck_split(s, p)
        _full_trucks(s, full, plant, p, alloc, flows, totals)
        if rest <= 0:
            continue
        if mode == "milkrun":
            by_region.setdefault(s["region"], []).append((s, rest))
        else:
            h = nearest_hub(s, hubs, plant, p)
            hub_of[s["id"]] = h["id"]
            by_hub.setdefault(h["id"], []).append((s, rest))
    for region in sorted(by_region):
        _run_routes(build_routes(by_region[region], plant, p), plant, "PLANT", p, alloc, flows, totals, True)
    hub_by_id = {h["id"]: h for h in hubs}
    for hid in sorted(by_hub):
        h = hub_by_id[hid]
        members = by_hub[hid]
        _run_routes(build_routes(members, h, p), h, hid, p, alloc, flows, totals, False)
        day_ldm = sum(load for _, load in members)
        day_t = sum(load * s["t_per_ldm"] for s, load in members)
        trucks = math.ceil(day_ldm / p["capacity_ldm"] - 1e-9)
        trips = trucks * p["runs_per_week"]
        km = road_km(h, plant, p)
        cost = trips * trip_cost(km, p, "linehaul_rate_km")
        co2 = trips * trip_co2_kg(km, day_t / trucks, p)
        handling = day_ldm * p["runs_per_week"] * p["handling_ldm"]
        for s, load in members:
            share = load / day_ldm
            alloc[s["id"]]["cost"] += (cost + handling) * share
            alloc[s["id"]]["co2_kg"] += co2 * share
        totals["cost"] += cost + handling
        totals["handling"] += handling
        totals["co2_kg"] += co2
        totals["trips"] += trips
        totals["arrivals"] += trips
        totals["vkm"] += trips * km
        flows.append({"kind": "linehaul", "path": [hid, "PLANT"], "trips": trips})
    co2_t = totals["co2_kg"] / 1000.0
    return {
        "cost_week": totals["cost"],
        "co2_t_week": co2_t,
        "trucks_week": totals["trips"],
        "plant_arrivals_week": totals["arrivals"],
        "vkm_week": totals["vkm"],
        "handling_week": totals["handling"],
        "objective": totals["cost"] + co2_t * p["co2_price_t"],
        "assign": dict(assign),
        "hub_of": hub_of,
        "alloc": alloc,
        "flows": flows,
    }


def _obj(alloc_row, p):
    return alloc_row["cost"] + alloc_row["co2_kg"] / 1000.0 * p["co2_price_t"]


def best_mix(suppliers, plant, hubs, p, pure=None, max_passes=4, extra_seeds=()):
    """Per-supplier mode choice. Seeds from the best of the pure designs, an
    allocation-based pick and any extra seeds, then accepts single-supplier
    mode changes that cut the network objective (cost + CO2 price).
    Result <= every pure design and every seed on that objective."""
    if pure is None:
        pure = {m: evaluate(suppliers, plant, hubs, {s["id"]: m for s in suppliers}, p) for m in MODES}
    seed_assign = {}
    for s in suppliers:
        seed_assign[s["id"]] = min(MODES, key=lambda m: (_obj(pure[m]["alloc"][s["id"]], p), MODES.index(m)))
    candidates = [pure[m] for m in MODES] + [evaluate(suppliers, plant, hubs, seed_assign, p)]
    candidates += [evaluate(suppliers, plant, hubs, a, p) for a in extra_seeds]
    best = candidates[0]
    for c in candidates[1:]:
        if c["objective"] < best["objective"] - 0.01:
            best = c
    for _ in range(max_passes):
        improved = False
        for s in suppliers:
            current = best["assign"][s["id"]]
            for m in MODES:
                if m == current:
                    continue
                trial_assign = dict(best["assign"])
                trial_assign[s["id"]] = m
                trial = evaluate(suppliers, plant, hubs, trial_assign, p)
                if trial["objective"] < best["objective"] - 0.01:
                    best = trial
                    current = m
                    improved = True
        if not improved:
            break
    return best


def run_scenario(network: dict, overrides: dict | None = None) -> dict:
    """Evaluate the three pure designs and the best mix for one parameter set."""
    p = params_with(overrides)
    sups, plant = network["suppliers"], network["plant"]
    hubs = [h for h in network["hubs"] if h.get("active", True)]
    pure = {m: evaluate(sups, plant, hubs, {s["id"]: m for s in sups}, p) for m in MODES}
    seeds = []
    if p["co2_price_t"] > 0:
        # the cost-only optimum is a strong starting point under a CO2 price
        p0 = dict(p, co2_price_t=0.0)
        pure0 = {m: evaluate(sups, plant, hubs, {s["id"]: m for s in sups}, p0) for m in MODES}
        seeds.append(best_mix(sups, plant, hubs, p0, pure0)["assign"])
    mix = best_mix(sups, plant, hubs, p, pure, extra_seeds=seeds)
    return {"params": p, "designs": {**pure, "bestmix": mix}}


def summary(result: dict) -> dict:
    """Compact, JSON-friendly view (drops per-supplier detail)."""
    out = {}
    for name, d in result["designs"].items():
        counts = {m: 0 for m in MODES}
        for m in d["assign"].values():
            counts[m] += 1
        out[name] = {
            "cost_week": round(d["cost_week"], 2),
            "co2_t_week": round(d["co2_t_week"], 4),
            "trucks_week": d["trucks_week"],
            "plant_arrivals_week": d["plant_arrivals_week"],
            "vkm_week": round(d["vkm_week"], 1),
            "objective": round(d["objective"], 2),
            "mode_counts": counts,
        }
    return out
