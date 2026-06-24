"""Build a gravitational-potential voxel grid for the Deep Field from GLADE+.

Task 2C.2 (the runtime loader) trilinearly interpolates this grid to estimate
the local Newtonian potential anywhere in the ±R_MAX cube without re-summing the
full galaxy catalog per query. This script produces that grid from the committed
GLADE+ sample (or, later, the BigQuery aggregation).

What it does:

* Reads galaxies (``ra, dec, dist_mpc, mass_msun``), converts spherical →
  Cartesian Mpc (mirrors ``build_tiles.py`` / ``process_galaxies.py``) and clips
  to the ±R_MAX cube.
* Voxelizes the ±R_MAX cube into N×N×N voxels and, at each VOXEL CENTER, sums the
  softened Newtonian potential MAGNITUDE over the galaxies:
  ``potential = Σ_i  G·M_i / sqrt(r_i² + softening²)``  (J/kg, positive),
  exactly mirroring ``app/services/physics.py`` (``local_potential`` /
  ``_potential_at``): positions Mpc→m via ``MPC_M``, masses Msun→kg via
  ``M_SUN_KG``, ``softening_m = softening_mpc · MPC_M``. Chunked over voxels to
  bound memory.
* Multiplies by ``--exaggeration`` (default **1.0**) and writes ``grid.npy`` +
  ``grid.json``.

IMPORTANT — RAW potential, not exaggerated. The committed grid stores the RAW
softened Newtonian potential magnitude (J/kg). The deepfield teaching
exaggeration is applied later, ONCE, in the physics model
(Task 2D.1's ``SCALES["deepfield"].exaggeration``). Applying it here too would
double-count, so ``--exaggeration`` defaults to 1.0 and the committed sample is
raw. (The flag exists only for experimentation; keep it 1.0 for the commit.)

Binary format (single source of truth):

* ``grid.npy``: NumPy **float32** array, shape ``(nz, ny, nx)``, indexed
  ``grid[iz, iy, ix]``, units J/kg (potential magnitude, positive).
* ``grid.json`` sidecar::

      {"bounds": [minx, miny, minz, maxx, maxy, maxz],
       "shape": [nz, ny, nx], "unit": "Mpc"}

Index → physical coordinate convention (VOXEL CENTERS) — must be unambiguous for
the 2C.2 trilinear interpolator. Per axis the cube ``[-R_MAX, +R_MAX]`` is split
into ``N`` equal voxels of width ``2·R_MAX / N``; the center of voxel ``i`` is::

    coord(i) = -R_MAX + (i + 0.5) · (2·R_MAX / N)        for i in 0..N-1

so ``ix`` maps to x, ``iy`` to y, ``iz`` to z, and the value at ``grid[iz,iy,ix]``
is the potential at ``(coord(ix), coord(iy), coord(iz))``. ``bounds`` are the cube
EXTENTS (faces at ±R_MAX), NOT voxel-center extremes.

Output is DETERMINISTIC: no RNG, fixed float32 dtype, fixed voxel-center grid —
same input → byte-identical ``grid.npy``. See
``docs/plans/003-cosmic-web-phase-2-deep-field.md``.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
DEFAULT_SAMPLE = BASE_DIR / "data" / "samples" / "glade_sample.csv.gz"
DEFAULT_OUT = BASE_DIR / "data" / "samples" / "deepfield" / "grid"

R_MAX_DEFAULT = 500.0        # Mpc — Deep Field cube bound (±R_MAX)
# Resolution for the COMMITTED sample grid. The full run uses N=64 (~1 MB);
# N=48 keeps grid.npy at 48^3 * 4 = 442,368 B (~432 KB), comfortably under the
# ~1 MB budget while staying finer than N=32 (128 KB). Committed grid is coarse.
N_DEFAULT = 48
SOFTENING_MPC_DEFAULT = 0.5  # matches cosmic scale's 0.5 * MPC_M in physics.py
EXAGGERATION_DEFAULT = 1.0   # RAW grid; deepfield exaggeration lives in SCALES (2D.1)

# Target float64 elements per chunk temporary (~64 MB). The per-batch arrays are
# (chunk × n_galaxies), so AUTO chunk = ELEMENT_BUDGET // n_galaxies keeps each
# numpy batch cache/RAM-friendly regardless of catalog size.
ELEMENT_BUDGET = 8_000_000

# Physics constants — reuse the exact values from app/services/physics.py.
G = 6.674e-11        # gravitational constant (m^3 kg^-1 s^-2)
MPC_M = 3.086e22     # m per megaparsec
M_SUN_KG = 1.989e30  # kg per solar mass


def load_sample(path: Path) -> pd.DataFrame:
    """Load the committed GLADE+ sample CSV (gzipped)."""
    if not path.exists():
        raise FileNotFoundError(f"GLADE+ sample not found: {path}")
    return pd.read_csv(path)


def load_bq() -> pd.DataFrame:
    """Read/aggregate the GLADE+ rows from BigQuery (Phase 2G).

    The full-catalog grid is built by aggregating the softened potential
    server-side; that path is wired by the Phase 2G GCP provisioning suite.
    """
    raise NotImplementedError(
        "--source bq is not a Python BigQuery client: the Phase 2G GCP suite "
        "materializes the glade_usable view to a CSV.gz and feeds it here via "
        "--in (see scripts/glade/gcp/20_build_assets.sh). Use --source sample "
        "(default) with --in for local/CI builds."
    )


def to_cartesian(df: pd.DataFrame) -> np.ndarray:
    """Spherical (ra, dec deg; dist_mpc) → Cartesian Mpc, matching build_tiles.py.

    x = d·cos(dec)·cos(ra), y = d·cos(dec)·sin(ra), z = d·sin(dec).
    """
    d = df["dist_mpc"].to_numpy(dtype=np.float64)
    ra = np.radians(df["ra"].to_numpy(dtype=np.float64))
    dec = np.radians(df["dec"].to_numpy(dtype=np.float64))
    x = d * np.cos(dec) * np.cos(ra)
    y = d * np.cos(dec) * np.sin(ra)
    z = d * np.sin(dec)
    return np.column_stack([x, y, z])


def prepare_galaxies(df: pd.DataFrame, r_max: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (xyz_mpc, mass_msun) for galaxies inside the ±r_max cube.

    Rows with non-finite position or mass, or non-positive mass, are dropped (a
    galaxy with no usable mass contributes nothing to the potential).
    """
    xyz = to_cartesian(df)
    mass = df["mass_msun"].to_numpy(dtype=np.float64)

    in_cube = np.all(np.abs(xyz) <= r_max, axis=1)
    finite = np.all(np.isfinite(xyz), axis=1) & np.isfinite(mass) & (mass > 0)
    keep = in_cube & finite
    return xyz[keep], mass[keep]


def voxel_centers(r_max: float, n: int) -> np.ndarray:
    """Per-axis voxel-CENTER coordinates (Mpc), length n.

    The cube [-r_max, +r_max] is split into n equal voxels of width
    2·r_max / n; center of voxel i is -r_max + (i + 0.5)·width.
    """
    width = (2.0 * r_max) / n
    return -r_max + (np.arange(n, dtype=np.float64) + 0.5) * width


def _potential_for_points(pts_m, sx, sy, sz, masses_kg, soft_sq, chunk):
    """Sum the softened Newtonian potential at each point (row of pts_m).

    Pure, serial reduction over ALL galaxies in array order. Returns a
    float64 ndarray of length len(pts_m). Math is identical to the original
    in-line loop; this is a structural extraction only.
    """
    out = np.empty(len(pts_m), dtype=np.float64)
    for i in range(0, len(pts_m), chunk):
        c = pts_m[i:i + chunk]
        dx = c[:, 0:1] - sx[None, :]
        dy = c[:, 1:2] - sy[None, :]
        dz = c[:, 2:3] - sz[None, :]
        r = np.sqrt(dx * dx + dy * dy + dz * dz + soft_sq)
        out[i:i + len(c)] = np.sum(G * masses_kg[None, :] / r, axis=1)
    return out


def build_grid(xyz_mpc: np.ndarray, mass_msun: np.ndarray, r_max: float,
               n: int, softening_mpc: float, exaggeration: float,
               chunk: int = 0, progress: bool = False) -> np.ndarray:
    """Voxelize the cube and sum the softened galaxy potential per voxel center.

    Returns a float32 array shape (n, n, n) indexed [iz, iy, ix], potential
    magnitude (J/kg, positive), multiplied by ``exaggeration``. Coordinates are
    converted Mpc→m and masses Msun→kg before summation, mirroring physics.py.
    Chunked over voxels to bound peak memory (~chunk × n_galaxies).

    ``chunk`` is the number of voxels processed per numpy batch:

    * ``chunk == 0`` (default) → AUTO: ``max(1, ELEMENT_BUDGET // n_galaxies)``,
      so each (chunk × n_galaxies) temporary stays near ELEMENT_BUDGET elements.
    * ``chunk > 0`` → used as-is.

    ``chunk`` NEVER affects the output: each voxel still reduces over the same
    galaxy array in the same order. Larger/smaller chunks only change how many
    voxels are processed per numpy batch → byte-identical ``grid.npy``.

    When ``progress=True``, periodic progress (voxels done/total, %, rate, ETA)
    is written to ``sys.stderr`` (never stdout). It is purely runtime logging and
    does not affect the output.
    """
    centers_m = voxel_centers(r_max, n) * MPC_M
    sx = xyz_mpc[:, 0] * MPC_M
    sy = xyz_mpc[:, 1] * MPC_M
    sz = xyz_mpc[:, 2] * MPC_M
    masses_kg = mass_msun * M_SUN_KG
    soft_sq = (softening_mpc * MPC_M) ** 2

    # Voxel centers in index order [iz, iy, ix] flattened to (n^3, 3) meters.
    # meshgrid(indexing="ij") over (z, y, x) → first axis iz, second iy, third ix.
    gz, gy, gx = np.meshgrid(centers_m, centers_m, centers_m, indexing="ij")
    pts = np.column_stack([gx.ravel(), gy.ravel(), gz.ravel()])  # (n^3, 3) m, x/y/z

    n_galaxies = len(masses_kg)
    if chunk <= 0:  # AUTO
        chunk = max(1, ELEMENT_BUDGET // max(1, n_galaxies))

    total = len(pts)
    if not progress:
        out = _potential_for_points(pts, sx, sy, sz, masses_kg, soft_sq, chunk)
    else:
        # Inline the same chunked loop so we can report after every batch. The
        # math/order is identical to _potential_for_points; only logging differs.
        out = np.empty(total, dtype=np.float64)
        start = time.monotonic()
        for i in range(0, total, chunk):
            sub = pts[i:i + chunk]
            out[i:i + len(sub)] = _potential_for_points(
                sub, sx, sy, sz, masses_kg, soft_sq, len(sub)
            )
            done = i + len(sub)
            elapsed = time.monotonic() - start
            rate = done / elapsed if elapsed > 0 else 0.0
            remaining = (total - done) / rate if rate > 0 else 0.0
            print(
                f"[build_grid] {done}/{total} voxels "
                f"({100.0 * done / total:.1f}%) … "
                f"{rate:.0f} vox/s ETA {remaining:.0f}s",
                file=sys.stderr,
            )

    out *= exaggeration
    return out.reshape(n, n, n).astype(np.float32)  # [iz, iy, ix]


def write_grid(grid: np.ndarray, r_max: float, out: Path) -> tuple[Path, Path]:
    """Write grid.npy (float32) + grid.json sidecar. Returns (npy, json) paths."""
    out.mkdir(parents=True, exist_ok=True)
    npy_path = out / "grid.npy"
    json_path = out / "grid.json"

    np.save(npy_path, grid)

    nz, ny, nx = grid.shape
    sidecar = {
        "bounds": [-r_max, -r_max, -r_max, r_max, r_max, r_max],
        "shape": [nz, ny, nx],
        "unit": "Mpc",
    }
    with open(json_path, "w") as f:
        json.dump(sidecar, f, indent=2)
        f.write("\n")
    return npy_path, json_path


def origin_voxel_index(r_max: float, n: int) -> tuple[int, int, int]:
    """(iz, iy, ix) of the voxel whose cell contains the origin (0,0,0)."""
    width = (2.0 * r_max) / n
    # Map a coordinate to its voxel index: floor((coord - (-r_max)) / width).
    idx = int((0.0 - (-r_max)) // width)
    idx = min(max(idx, 0), n - 1)
    return idx, idx, idx


def verify(grid: np.ndarray, r_max: float, n: int) -> dict:
    """Validate the grid and assert the deepest-void advantage condition.

    Since the deepfield dilation isn't registered yet (Task 2D.1), we assert the
    equivalent guarantee: the MINIMUM grid potential is strictly LESS than the
    potential at the origin/Earth voxel. With f ∝ sqrt(1 − exa·2Φ/c²), a lower Φ
    yields a larger f, so the deepest void's clock_advantage = f_void / f_earth
    will be > 1 once any positive exaggeration is applied.
    """
    assert np.all(np.isfinite(grid)), "grid contains non-finite values"

    gmin = float(grid.min())
    gmax = float(grid.max())

    centers = voxel_centers(r_max, n)
    flat_argmin = int(np.argmin(grid))
    iz, iy, ix = np.unravel_index(flat_argmin, grid.shape)
    argmin_coord = (float(centers[ix]), float(centers[iy]), float(centers[iz]))

    oz, oy, ox = origin_voxel_index(r_max, n)
    origin_val = float(grid[oz, oy, ox])

    assert gmin < origin_val, (
        f"min potential {gmin:.6e} not below origin-voxel potential "
        f"{origin_val:.6e}; deepest-void advantage would not exceed 1"
    )
    return {
        "min": gmin,
        "max": gmax,
        "origin_val": origin_val,
        "argmin_coord": argmin_coord,
        "argmin_index": (int(iz), int(iy), int(ix)),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Build a gravitational-potential voxel grid for the Deep Field."
    )
    p.add_argument("--source", choices=["sample", "bq"], default="sample",
                   help="input source (default: sample). bq is wired in Phase 2G.")
    p.add_argument("--in", dest="sample_path", default=str(DEFAULT_SAMPLE),
                   help="path to the GLADE+ sample csv.gz (--source sample).")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="output grid dir.")
    p.add_argument("--r-max", type=float, default=R_MAX_DEFAULT,
                   help="cube bound in Mpc (default 500).")
    p.add_argument("--n", type=int, default=N_DEFAULT,
                   help="grid resolution per axis, N (default 48 for the sample; "
                        "full run uses 64).")
    p.add_argument("--softening-mpc", type=float, default=SOFTENING_MPC_DEFAULT,
                   help="softening length in Mpc (default 0.5, matches cosmic scale).")
    p.add_argument("--exaggeration", type=float, default=EXAGGERATION_DEFAULT,
                   help="multiply stored potential (default 1.0 = RAW; keep 1.0 "
                        "for the committed grid — exaggeration lives in SCALES).")
    p.add_argument("--chunk", type=int, default=0,
                   help="voxels per batch; 0 = auto from ELEMENT_BUDGET.")
    prog = p.add_mutually_exclusive_group()
    prog.add_argument("--progress", dest="progress", action="store_true",
                      help="emit periodic progress to stderr.")
    prog.add_argument("--quiet", dest="progress", action="store_false",
                      help="suppress progress output (default).")
    p.set_defaults(progress=False)
    args = p.parse_args(argv)

    out = Path(args.out)

    if args.source == "bq":
        df = load_bq()  # raises NotImplementedError (Phase 2G)
    else:
        df = load_sample(Path(args.sample_path))

    xyz, mass = prepare_galaxies(df, args.r_max)
    grid = build_grid(xyz, mass, args.r_max, args.n, args.softening_mpc,
                      args.exaggeration, chunk=args.chunk, progress=args.progress)
    npy_path, json_path = write_grid(grid, args.r_max, out)
    stats = verify(grid, args.r_max, args.n)

    print(f"source:        {args.source}")
    print(f"galaxies:      {len(xyz)} in ±{args.r_max:g} Mpc cube")
    print(f"resolution N:  {args.n}  shape (nz,ny,nx)={grid.shape}")
    print(f"softening:     {args.softening_mpc:g} Mpc")
    print(f"exaggeration:  {args.exaggeration:g} (1.0 = RAW)")
    print(f"grid.npy:      {npy_path}  ({npy_path.stat().st_size:,} bytes)")
    print(f"grid.json:     {json_path}")
    print(f"potential J/kg min={stats['min']:.6e}  max={stats['max']:.6e}")
    print(f"origin voxel:  Φ={stats['origin_val']:.6e}  index(iz,iy,ix)="
          f"{origin_voxel_index(args.r_max, args.n)}")
    print(f"argmin voxel:  index(iz,iy,ix)={stats['argmin_index']}  "
          f"coord(x,y,z) Mpc={tuple(round(v, 3) for v in stats['argmin_coord'])}")
    print(f"verify:        min < origin  ->  deepest-void clock_advantage > 1  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
