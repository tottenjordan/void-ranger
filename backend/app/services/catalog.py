import json
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "stars.json"
SOLAR_MASS_KG = 1.989e30


@lru_cache(maxsize=1)
def load_stars() -> list[dict]:
    """Load the processed star catalog once and cache it.

    Each star is {x, y, z, size, m} where x/y/z are parsecs and m is the
    estimated mass in solar masses.
    """
    with open(DATA_PATH) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_star_arrays():
    """Cached NumPy arrays for fast gravitational-potential sums.

    Returns (xs, ys, zs) in parsecs and masses in kilograms.
    """
    stars = load_stars()
    xs = np.array([s["x"] for s in stars], dtype=float)
    ys = np.array([s["y"] for s in stars], dtype=float)
    zs = np.array([s["z"] for s in stars], dtype=float)
    masses_kg = np.array([s["m"] for s in stars], dtype=float) * SOLAR_MASS_KG
    return xs, ys, zs, masses_kg
