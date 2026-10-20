"""Seeded synthetic inbound network for a fictional Contoso Logistics client:
one automotive OEM plant in central Germany, 60 suppliers across Europe and
three candidate cross-dock hubs. Reproducible with the same seed."""
from __future__ import annotations

import random

PLANT = {"id": "PLANT", "name": "OEM plant (central Germany)", "lat": 50.90, "lon": 10.20}

HUBS = [
    {"id": "HUB-IT", "name": "Hub northern Italy", "lat": 45.55, "lon": 10.60, "active": True},
    {"id": "HUB-CZ", "name": "Hub Czechia", "lat": 49.75, "lon": 16.10, "active": True},
    {"id": "HUB-FR", "name": "Hub eastern France", "lat": 47.20, "lon": 4.90, "active": True},
]

# region code, centre lat, centre lon, supplier count
REGIONS = [
    ("DE-S", 48.70, 10.30, 9),
    ("DE-W", 51.30, 7.20, 8),
    ("BNL", 51.10, 4.60, 5),
    ("FR-E", 48.20, 5.80, 6),
    ("IT-N", 45.50, 10.20, 8),
    ("CZ", 49.70, 16.40, 7),
    ("PL-S", 50.40, 19.20, 6),
    ("ES-N", 42.60, -2.40, 5),
    ("HU-AT", 47.60, 17.80, 6),
]


def generate(seed: int = 3) -> dict:
    rng = random.Random(seed)
    suppliers = []
    n = 0
    for code, lat, lon, count in REGIONS:
        for _ in range(count):
            n += 1
            tier = rng.random()
            if tier < 0.2:
                ldm = rng.uniform(20, 60)
                freq = 5
            elif tier < 0.7:
                ldm = rng.uniform(6, 20)
                freq = rng.choice([2, 3, 5])
            else:
                ldm = rng.uniform(1, 6)
                freq = rng.choice([1, 2])
            suppliers.append({
                "id": f"S{n:02d}",
                "region": code,
                "lat": round(lat + rng.gauss(0, 0.7), 4),
                "lon": round(lon + rng.gauss(0, 1.0), 4),
                "ldm_week": round(ldm, 2),
                "freq": freq,
                "t_per_ldm": round(rng.uniform(0.5, 1.5), 2),
            })
    return {"seed": seed, "plant": dict(PLANT), "hubs": [dict(h) for h in HUBS], "suppliers": suppliers}
