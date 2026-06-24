"""Build an octree LOD tileset for the Deep Field from the GLADE+ sample.

The Deep Field scale streams precomputed level-of-detail (LOD) tiles into a
Three.js point cloud: coarse tiles load first, finer tiles refine on zoom. This
script builds that tileset from the committed GLADE+ sample (or, later, the
BigQuery view).

What it does:

* Reads galaxies (``ra, dec, dist_mpc`` + magnitudes), converts spherical →
  Cartesian Mpc (mirrors ``process_galaxies.py``), and clips to the ±R_MAX cube.
* Ranks every galaxy by apparent brightness — canonical W1, falling back to B
  then K (lower mag = brighter), matching ``scripts/glade/README.md``.
* Recursively space-partitions the cube into an octree. Each node keeps its
  brightest ``cap`` galaxies (a prefix of a node is therefore a valid
  downsample); a node recurses into 8 octant children only while it holds more
  than ``cap`` points and depth < ``max_depth``.
* Writes each node's kept ``x,y,z`` as little-endian Float32 ``tiles/<id>.bin``
  (3 floats/galaxy, no header) plus ``tiles/manifest.json``.

Node ids: root ``"0"``; a child appends its octant digit 0..7 (e.g. ``"00"``,
``"01"``). Octant bit order: bit 0 = x, bit 1 = y, bit 2 = z (0 = low half).

Output is DETERMINISTIC: no RNG, stable mergesort on the brightness key, fixed
``<f4`` dtype — same input → byte-identical tiles. See
``docs/plans/003-cosmic-web-phase-2-deep-field.md``.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
DEFAULT_SAMPLE = BASE_DIR / "data" / "samples" / "glade_sample.csv.gz"
DEFAULT_OUT = BASE_DIR / "data" / "samples" / "deepfield" / "tiles"

R_MAX_DEFAULT = 500.0   # Mpc — Deep Field cube bound (±R_MAX)
MAX_DEPTH_DEFAULT = 6   # octree recursion cap
CAP_DEFAULT = 40000     # max points kept per node (C)

# Canonical brightness for ranking: prefer W1, fall back to B then K (lower mag =
# brighter). Documented in scripts/glade/README.md.
RANKING_MAGS = ("w1_mag", "b_mag", "k_mag")


def load_sample(path: Path) -> pd.DataFrame:
    """Load the committed GLADE+ sample CSV (gzipped)."""
    if not path.exists():
        raise FileNotFoundError(f"GLADE+ sample not found: {path}")
    return pd.read_csv(path)


def load_bq() -> pd.DataFrame:
    """Read the GLADE+ rows from the BigQuery view (Phase 2G)."""
    raise NotImplementedError(
        "--source bq is wired by the Phase 2G GCP provisioning suite; "
        "use --source sample (default) for local/CI builds."
    )


def to_cartesian(df: pd.DataFrame) -> np.ndarray:
    """Spherical (ra, dec deg; dist_mpc) → Cartesian Mpc, matching process_galaxies.py.

    x = d·cos(dec)·cos(ra), y = d·cos(dec)·sin(ra), z = d·sin(dec).
    """
    d = df["dist_mpc"].to_numpy(dtype=np.float64)
    ra = np.radians(df["ra"].to_numpy(dtype=np.float64))
    dec = np.radians(df["dec"].to_numpy(dtype=np.float64))
    x = d * np.cos(dec) * np.cos(ra)
    y = d * np.cos(dec) * np.sin(ra)
    z = d * np.sin(dec)
    return np.column_stack([x, y, z])


def ranking_mag(df: pd.DataFrame) -> np.ndarray:
    """Apparent ranking magnitude: W1, else B, else K. NaN if all three missing."""
    rank = np.full(len(df), np.nan, dtype=np.float64)
    for col in RANKING_MAGS:
        vals = df[col].to_numpy(dtype=np.float64)
        fill = np.isnan(rank) & ~np.isnan(vals)
        rank[fill] = vals[fill]
    return rank


def prepare_points(df: pd.DataFrame, r_max: float) -> np.ndarray:
    """Return points sorted brightest-first, clipped to the ±r_max cube.

    Shape (N, 3) float64: columns x, y, z (Mpc). Rows missing all ranking mags
    are dropped; remaining rows are stably sorted ascending by ranking mag so a
    prefix is always the brightest subset.
    """
    xyz = to_cartesian(df)
    mag = ranking_mag(df)

    in_cube = np.all(np.abs(xyz) <= r_max, axis=1)
    has_rank = ~np.isnan(mag)
    keep = in_cube & has_rank
    xyz = xyz[keep]
    mag = mag[keep]

    # Stable sort ascending by brightness (lowest mag = brightest first).
    order = np.argsort(mag, kind="stable")
    return xyz[order]


def octant_bounds(bounds: np.ndarray, octant: int) -> np.ndarray:
    """Child bounds for an octant. bounds = [minx,miny,minz,maxx,maxy,maxz]."""
    lo = bounds[:3]
    hi = bounds[3:]
    mid = (lo + hi) / 2.0
    child_lo = np.where([(octant >> i) & 1 for i in range(3)], mid, lo)
    child_hi = np.where([(octant >> i) & 1 for i in range(3)], hi, mid)
    return np.concatenate([child_lo, child_hi])


def points_in_bounds(points: np.ndarray, bounds: np.ndarray,
                     upper_inclusive: np.ndarray) -> np.ndarray:
    """Boolean mask of points within a node's bounds, partitioned PER AXIS.

    Each axis is half-open ``[lo, hi)`` so that on every interior split plane a
    point has exactly one owner among sibling octants (no duplication). The
    upper face is inclusive ONLY on axes where it coincides with the global
    +R_MAX cube boundary (``upper_inclusive[axis]`` True), so a galaxy sitting
    exactly on +R_MAX in one or more axes is still kept by the root and routed
    to a single leaf (no silent drop). ``upper_inclusive`` is a length-3 bool
    array; the partition is otherwise exact (each point in exactly one node per
    LOD level).
    """
    lo = bounds[:3]
    hi = bounds[3:]
    ge = points >= lo
    lt = points < hi
    hi_ok = lt | (upper_inclusive & (points == hi))
    return np.all(ge & hi_ok, axis=1)


def build_octree(points: np.ndarray, bounds: np.ndarray, cap: int,
                 max_depth: int, node_id: str, nodes: dict,
                 upper_inclusive: np.ndarray) -> None:
    """Recursively fill ``nodes`` with octree LOD nodes.

    ``points`` are already sorted brightest-first. The node keeps its brightest
    ``cap`` and recurses into 8 octants only when it holds more than ``cap`` and
    depth < max_depth. A child node is created only if it would hold ≥ 1 point.

    ``upper_inclusive`` is a length-3 bool array marking which of this node's
    upper faces coincide with the global +R_MAX cube boundary. A child inherits
    that inclusiveness on an axis only when it takes the HIGH half there; low-half
    children get a strict ``[lo, hi)`` interior plane (single owner).
    """
    depth = len(node_id) - 1  # root "0" => depth 0
    kept = points[:cap]

    children: list[str] = []
    should_recurse = len(points) > cap and depth < max_depth
    if should_recurse:
        for octant in range(8):
            child_bounds = octant_bounds(bounds, octant)
            high_half = np.array([(octant >> i) & 1 for i in range(3)], dtype=bool)
            child_upper = upper_inclusive & high_half
            mask = points_in_bounds(points, child_bounds, child_upper)
            if not mask.any():
                continue
            child_id = node_id + str(octant)
            children.append(child_id)
            build_octree(points[mask], child_bounds, cap, max_depth,
                         child_id, nodes, child_upper)

    nodes[node_id] = {
        "bounds": [round(float(b), 6) for b in bounds],
        "count": int(len(kept)),
        "children": children,
        "file": f"{node_id}.bin",
        "_points": kept,  # stripped before serialization
    }


def write_tiles(nodes: dict, out: Path) -> int:
    """Write each node's points as little-endian Float32 <id>.bin. Returns bytes."""
    out.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for node_id, node in nodes.items():
        pts = node.pop("_points")
        buf = np.ascontiguousarray(pts, dtype="<f4")
        path = out / node["file"]
        buf.tofile(path)
        total_bytes += path.stat().st_size

        # Endianness round-trip self-check: the JS frontend reads Float32Array
        # (little-endian on all target platforms), so assert what we wrote reads
        # back identically as <f4.
        back = np.fromfile(path, dtype="<f4")
        np.testing.assert_array_equal(back, buf.reshape(-1), err_msg=str(path))
    return total_bytes


def write_manifest(nodes: dict, root: str, out: Path) -> Path:
    """Write tiles/manifest.json in the documented shape (sorted keys, no _points)."""
    manifest = {
        "unit": "Mpc",
        "root": root,
        "nodes": {nid: nodes[nid] for nid in sorted(nodes)},
    }
    path = out / "manifest.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def validate(out: Path, cap: int) -> dict:
    """Validate a written tileset against the manifest. Returns summary stats."""
    with open(out / "manifest.json") as f:
        manifest = json.load(f)

    nodes = manifest["nodes"]
    root = manifest["root"]
    assert manifest["unit"] == "Mpc", "unit must be Mpc"
    assert root in nodes, f"root {root!r} missing from nodes"
    assert nodes[root]["count"] <= cap, "root count exceeds cap"

    sum_node_counts = 0
    for nid, node in nodes.items():
        bin_path = out / node["file"]
        assert bin_path.exists(), f"missing tile: {bin_path}"
        size = bin_path.stat().st_size
        assert size == node["count"] * 12, (
            f"{nid}: {size} bytes != count {node['count']} × 12"
        )
        for child in node["children"]:
            assert child in nodes, f"{nid}: child {child!r} has no node"
        # leaf prefix check: a child id extends the parent id by one digit.
        for child in node["children"]:
            assert child.startswith(nid) and len(child) == len(nid) + 1, (
                f"{nid}: malformed child id {child!r}"
            )
        sum_node_counts += node["count"]

    return {
        "nodes": len(nodes),
        "root_count": nodes[root]["count"],
        # Sum of per-node counts across all LOD levels — NOT unique galaxies;
        # coarse and fine tiles intentionally overlap (a parent re-lists points
        # that also appear in its children).
        "sum_node_counts": sum_node_counts,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build an octree LOD tileset for the Deep Field.")
    p.add_argument("--source", choices=["sample", "bq"], default="sample",
                   help="input source (default: sample). bq is wired in Phase 2G.")
    p.add_argument("--in", dest="sample_path", default=str(DEFAULT_SAMPLE),
                   help="path to the GLADE+ sample csv.gz (--source sample).")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="output tiles dir.")
    p.add_argument("--r-max", type=float, default=R_MAX_DEFAULT,
                   help="cube bound in Mpc (default 500).")
    p.add_argument("--max-depth", type=int, default=MAX_DEPTH_DEFAULT,
                   help="max octree depth (default 6).")
    p.add_argument("--cap", type=int, default=CAP_DEFAULT,
                   help="max points kept per node, C (default 40000).")
    args = p.parse_args(argv)

    out = Path(args.out)
    r_max = args.r_max  # argparse already coerces --r-max to float

    if args.source == "bq":
        df = load_bq()  # raises NotImplementedError (Phase 2G)
    else:
        df = load_sample(Path(args.sample_path))

    points = prepare_points(df, r_max)

    root_bounds = np.array([-r_max, -r_max, -r_max, r_max, r_max, r_max], dtype=np.float64)
    # The root's three upper faces ARE the global +R_MAX boundary → inclusive.
    root_upper = np.array([True, True, True])
    nodes: dict = {}
    build_octree(points, root_bounds, args.cap, args.max_depth, "0", nodes, root_upper)

    total_bytes = write_tiles(nodes, out)
    manifest_path = write_manifest(nodes, "0", out)
    stats = validate(out, args.cap)

    print(f"source:       {args.source}")
    print(f"galaxies:     {len(points)} in ±{r_max:g} Mpc cube")
    print(f"nodes:        {stats['nodes']}")
    print(f"root count:   {stats['root_count']} (cap {args.cap})")
    print(f"sum node cnt: {stats['sum_node_counts']} (LOD overlap; not unique galaxies)")
    print(f"tile bytes:   {total_bytes:,}")
    print(f"manifest:     {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
