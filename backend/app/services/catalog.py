import json
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_PATH = DATA_DIR / "stars.json"
GALAXIES_PATH = DATA_DIR / "galaxies.json"
SOLAR_MASS_KG = 1.989e30


@lru_cache(maxsize=1)
def load_stars() -> list[dict]:
    """Load the processed star catalog once and cache it.

    Each star is {x, y, z, size, m, name, desig, mag, con} where x/y/z are
    parsecs, m is the estimated mass in solar masses, name is the proper name
    (empty for most stars), desig is the Bayer/Flamsteed-or-catalog fallback,
    mag is apparent magnitude, and con is the constellation abbreviation.
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


@lru_cache(maxsize=1)
def load_galaxies() -> list[dict]:
    """Load the processed galaxy catalog once and cache it.

    Each galaxy is {x, y, z, size, m, name, desig, mag, dist, cz} where x/y/z
    are megaparsecs, m is the estimated mass in solar masses, name is the proper
    name (empty for most galaxies), desig is the catalog designation, mag is
    apparent magnitude, dist is distance in Mpc, and cz is recession velocity.
    """
    with open(GALAXIES_PATH) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_galaxy_arrays():
    """Cached NumPy arrays for fast gravitational-potential sums.

    Returns (xs, ys, zs) in megaparsecs and masses in kilograms — same shape as
    load_star_arrays, just at the cosmic scale.
    """
    galaxies = load_galaxies()
    xs = np.array([g["x"] for g in galaxies], dtype=float)
    ys = np.array([g["y"] for g in galaxies], dtype=float)
    zs = np.array([g["z"] for g in galaxies], dtype=float)
    masses_kg = np.array([g["m"] for g in galaxies], dtype=float) * SOLAR_MASS_KG
    return xs, ys, zs, masses_kg


def load_arrays(scale: str = "solar"):
    """Dispatch to the right catalog arrays for the given scale.

    "solar" -> star catalog (parsecs); "cosmic" -> galaxy catalog (megaparsecs).
    """
    if scale == "solar":
        return load_star_arrays()
    if scale == "cosmic":
        return load_galaxy_arrays()
    raise ValueError(f"unknown scale: {scale!r}")
