import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_PATH = DATA_DIR / "stars.json"
GALAXIES_PATH = DATA_DIR / "galaxies.json"
SOLAR_MASS_KG = 1.989e30

# Deep Field potential grid (see backend/scripts/glade/build_grid.py). Defaults
# to the committed N=48 sample; override the directory via DEEPFIELD_GRID_DIR.
DEEPFIELD_GRID_DIR = DATA_DIR / "samples" / "deepfield" / "grid"
DEEPFIELD_GRID_DIR_ENV = "DEEPFIELD_GRID_DIR"


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


@dataclass(frozen=True)
class PotentialGrid:
    """A voxelized gravitational-potential grid (Deep Field).

    values: ndarray shape (nz, ny, nx), indexed values[iz, iy, ix], holding the
        potential magnitude (J/kg, positive) at each voxel CENTER.
    bounds: (minx, miny, minz, maxx, maxy, maxz) cube FACES in Mpc (not
        voxel-center extremes). Voxel center along an axis [lo, hi] with n voxels
        is lo + (i + 0.5) * (hi - lo) / n.
    shape: (nz, ny, nx) — same as values.shape.
    """

    values: np.ndarray
    bounds: tuple[float, float, float, float, float, float]
    shape: tuple[int, int, int]


def _deepfield_grid_dir() -> Path:
    """Resolve the Deep Field grid directory (env override or committed sample)."""
    override = os.environ.get(DEEPFIELD_GRID_DIR_ENV)
    return Path(override) if override else DEEPFIELD_GRID_DIR


@lru_cache(maxsize=4)
def _load_grid(grid_dir: Path) -> PotentialGrid:
    """Load + cache a potential grid from a resolved directory.

    Cached on the resolved grid_dir so different directories (e.g. an env
    override pointing at a temp grid) cache independently, and a change to
    DEEPFIELD_GRID_DIR is honored on the next public call.
    """
    values = np.load(grid_dir / "grid.npy")
    with open(grid_dir / "grid.json") as f:
        sidecar = json.load(f)
    bounds = tuple(float(b) for b in sidecar["bounds"])
    shape = tuple(int(s) for s in sidecar["shape"])
    if values.shape != shape:
        raise ValueError(
            f"grid.npy shape {values.shape} != grid.json shape {shape}"
        )
    # Freeze the shared cached array so a caller can't mutate it in place.
    values.setflags(write=False)
    return PotentialGrid(values=values, bounds=bounds, shape=shape)


def load_potential_grid(scale: str = "deepfield") -> PotentialGrid:
    """Load the potential grid for the given scale (cached per grid directory).

    Only "deepfield" has a grid; "solar"/"cosmic" sum their catalogs directly.
    Reads grid.npy (float32, shape (nz, ny, nx)) + grid.json sidecar from the
    directory given by DEEPFIELD_GRID_DIR (env) or the committed sample default.
    The grid directory is resolved here (so env changes are honored) and the
    actual load is delegated to a cache keyed on that directory.
    """
    if scale != "deepfield":
        raise ValueError(f"no potential grid for scale: {scale!r}")
    return _load_grid(_deepfield_grid_dir())
