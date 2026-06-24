"""Tests for the Deep Field octree LOD tile builder (scripts/glade/build_tiles.py).

Covers the committed sample tileset (manifest validity, .bin sizes, root cap)
plus an in-process small-cap build that exercises octree recursion, the
brightness-prefix property, determinism, and the little-endian Float32 round
trip the JS frontend relies on.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.glade import build_tiles  # noqa: E402

TILES_DIR = BACKEND_DIR / "data" / "samples" / "deepfield" / "tiles"
SAMPLE = BACKEND_DIR / "data" / "samples" / "glade_sample.csv.gz"


def _load_manifest(tiles_dir: Path) -> dict:
    with open(tiles_dir / "manifest.json") as f:
        return json.load(f)


def test_committed_tileset_exists():
    assert (TILES_DIR / "manifest.json").exists()
    assert (TILES_DIR / "0.bin").exists()


def test_committed_manifest_shape():
    m = _load_manifest(TILES_DIR)
    assert m["unit"] == "Mpc"
    assert m["root"] == "0"
    assert "0" in m["nodes"]


def test_committed_validates():
    # validate() asserts: root present, children exist, bytes == count×12,
    # root count ≤ cap. Use the default cap.
    stats = build_tiles.validate(TILES_DIR, build_tiles.CAP_DEFAULT)
    assert stats["root_count"] <= build_tiles.CAP_DEFAULT
    assert stats["nodes"] >= 1


def test_committed_bin_sizes_match_counts():
    m = _load_manifest(TILES_DIR)
    for nid, node in m["nodes"].items():
        size = (TILES_DIR / node["file"]).stat().st_size
        assert size == node["count"] * 12, nid


def _build(tmp_path: Path, cap: int) -> Path:
    out = tmp_path / "tiles"
    build_tiles.main(["--source", "sample", "--in", str(SAMPLE),
                      "--out", str(out), "--cap", str(cap)])
    return out


def test_octree_recurses_with_small_cap(tmp_path):
    out = _build(tmp_path, cap=2000)
    m = _load_manifest(out)
    assert len(m["nodes"]) > 1, "small cap should force octree recursion"
    assert m["nodes"]["0"]["count"] == 2000
    # Every child id exists and extends its parent by exactly one octant digit.
    for nid, node in m["nodes"].items():
        for child in node["children"]:
            assert child in m["nodes"]
            assert child.startswith(nid) and len(child) == len(nid) + 1
            assert child[-1] in "01234567"


def test_small_cap_validates(tmp_path):
    out = _build(tmp_path, cap=2000)
    build_tiles.validate(out, 2000)  # raises on any inconsistency


def test_brightness_prefix_property(tmp_path):
    """The root tile must be the globally brightest `cap` galaxies, in order.

    prepare_points() returns points sorted brightest-first, so the root .bin
    must equal that brightest prefix — proving a truncated prefix is a valid
    downsample.
    """
    df = build_tiles.load_sample(SAMPLE)
    pts = build_tiles.prepare_points(df, build_tiles.R_MAX_DEFAULT)
    assert len(pts) > 0
    out = _build(tmp_path, cap=5000)
    root = np.fromfile(out / "0.bin", dtype="<f4").reshape(-1, 3)
    np.testing.assert_array_equal(root, pts[:5000].astype("<f4"))


def test_endianness_round_trip(tmp_path):
    out = _build(tmp_path, cap=3000)
    m = _load_manifest(out)
    for nid, node in m["nodes"].items():
        raw = (out / node["file"]).read_bytes()
        le = np.frombuffer(raw, dtype="<f4")
        assert le.size == node["count"] * 3
        # Big-endian interpretation must differ (sanity that endianness matters),
        # unless the tile is empty.
        if node["count"]:
            be = np.frombuffer(raw, dtype=">f4")
            assert not np.array_equal(le, be)


def test_deterministic(tmp_path):
    a = _build(tmp_path / "a", cap=2000)
    b = _build(tmp_path / "b", cap=2000)
    for f in a.iterdir():
        assert f.read_bytes() == (b / f.name).read_bytes(), f.name


def test_bq_source_not_implemented():
    with pytest.raises(NotImplementedError):
        build_tiles.main(["--source", "bq"])


def _leaf_ids(manifest: dict) -> list[str]:
    return [nid for nid, node in manifest["nodes"].items() if not node["children"]]


def test_partition_is_exact_no_loss_no_dup(tmp_path):
    """Union of all LEAF tiles == every prepared point, exactly once.

    Internal nodes hold a capped (overlapping) prefix, but the LEAVES tile the
    space disjointly: each prepared galaxy must land in exactly one leaf — no
    point silently dropped on a boundary, none double-counted across siblings.
    """
    df = build_tiles.load_sample(SAMPLE)
    pts = build_tiles.prepare_points(df, build_tiles.R_MAX_DEFAULT)
    cap = 2000
    out = _build(tmp_path, cap=cap)
    m = _load_manifest(out)

    leaves = _leaf_ids(m)
    union = []
    for nid in leaves:
        node = m["nodes"][nid]
        # Leaf holds ≤ cap points (no recursion happened), so it is not truncated.
        assert node["count"] <= cap
        arr = np.fromfile(out / node["file"], dtype="<f4").reshape(-1, 3)
        union.append(arr)
    union = np.concatenate(union) if union else np.empty((0, 3), dtype="<f4")

    # Same total count: no loss, no duplication across the disjoint leaf cover.
    assert len(union) == len(pts)

    # Set-equality on rows (order differs across leaves). Compare as <f4 since
    # the tiles are stored at float32 precision.
    expected = pts.astype("<f4")
    a = {tuple(r) for r in union}
    b = {tuple(r) for r in expected}
    assert a == b


def test_boundary_and_center_each_single_owner(tmp_path):
    """An outer +R_MAX face point and the cube center each route to exactly one
    node per LOD level (regression for the per-axis partition fix)."""
    r = build_tiles.R_MAX_DEFAULT
    root_bounds = np.array([-r, -r, -r, r, r, r], dtype=np.float64)
    root_upper = np.array([True, True, True])

    for p in ([r, 50.0, 50.0], [0.0, 0.0, 0.0]):
        pt = np.array([p], dtype=np.float64)
        # Kept by the root.
        assert build_tiles.points_in_bounds(pt, root_bounds, root_upper).all()
        # Routed to exactly one of the 8 octants.
        owners = 0
        for octant in range(8):
            cb = build_tiles.octant_bounds(root_bounds, octant)
            high = np.array([(octant >> i) & 1 for i in range(3)], dtype=bool)
            cu = root_upper & high
            if build_tiles.points_in_bounds(pt, cb, cu).all():
                owners += 1
        assert owners == 1, f"{p} had {owners} octant owners (want 1)"
