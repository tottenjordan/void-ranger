"""Tests for the Deep Field potential-grid loader + trilinear interpolation.

Convention (authoritative: backend/scripts/glade/build_grid.py docstring):
- grid.npy float32 shape (nz, ny, nx), indexed grid[iz, iy, ix].
- grid.json bounds = cube FACES [minx,miny,minz,maxx,maxy,maxz]; shape [nz,ny,nx].
- Voxel CENTER along an axis [lo, hi] with n voxels:
    center(i) = lo + (i + 0.5) * (hi - lo) / n
- Axis order: pts[:,0]=x->ix, pts[:,1]=y->iy, pts[:,2]=z->iz.
"""
import json

import numpy as np
import pytest

from app.services.catalog import (
    DEEPFIELD_GRID_DIR_ENV,
    load_potential_grid,
)
from app.services.physics import _grid_potential_at


def _center(lo: float, hi: float, n: int, i: int) -> float:
    return lo + (i + 0.5) * (hi - lo) / n


# --- Loader -----------------------------------------------------------------

def test_grid_loads_shape_dtype_bounds():
    grid = load_potential_grid("deepfield")
    # shape matches grid.json (the committed N=48 sample)
    assert grid.shape == (48, 48, 48)
    assert grid.values.shape == (48, 48, 48)
    # bounds are the cube faces, ±500 Mpc
    assert grid.bounds == (-500.0, -500.0, -500.0, 500.0, 500.0, 500.0)
    # values finite and positive (potential magnitude, J/kg)
    assert np.all(np.isfinite(grid.values))
    assert np.all(grid.values > 0)
    # grid.npy is float32 by contract (build_grid.py).
    assert grid.values.dtype == np.float32


def test_grid_loader_is_cached():
    assert load_potential_grid("deepfield") is load_potential_grid("deepfield")


def test_grid_loader_rejects_non_deepfield_scales():
    with pytest.raises(ValueError):
        load_potential_grid("solar")
    with pytest.raises(ValueError):
        load_potential_grid("cosmic")


def test_grid_loader_honors_env_override(tmp_path, monkeypatch):
    # Write a tiny 2x2x2 grid to a temp dir, point DEEPFIELD_GRID_DIR at it, and
    # confirm the loader picks it up (also guards the per-dir cache: an env
    # change is honored rather than serving the first-call default).
    tiny = np.arange(8, dtype=np.float32).reshape(2, 2, 2) + 1.0
    np.save(tmp_path / "grid.npy", tiny)
    sidecar = {
        "bounds": [-1.0, -1.0, -1.0, 1.0, 1.0, 1.0],
        "shape": [2, 2, 2],
        "unit": "Mpc",
    }
    (tmp_path / "grid.json").write_text(json.dumps(sidecar))

    monkeypatch.setenv(DEEPFIELD_GRID_DIR_ENV, str(tmp_path))
    grid = load_potential_grid("deepfield")
    assert grid.shape == (2, 2, 2)
    assert grid.bounds == (-1.0, -1.0, -1.0, 1.0, 1.0, 1.0)
    assert np.array_equal(grid.values, tiny)

    # With the env cleared, the default committed sample loads again.
    monkeypatch.delenv(DEEPFIELD_GRID_DIR_ENV, raising=False)
    default = load_potential_grid("deepfield")
    assert default.shape == (48, 48, 48)


# --- Trilinear interpolation ------------------------------------------------

def test_grid_potential_at_voxel_center_equals_stored_value():
    grid = load_potential_grid("deepfield")
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape

    # Evaluate at the global-min voxel's center -> should equal the stored min.
    iz, iy, ix = np.unravel_index(int(np.argmin(grid.values)), grid.shape)
    stored = float(grid.values[iz, iy, ix])
    cx = _center(minx, maxx, nx, int(ix))
    cy = _center(miny, maxy, ny, int(iy))
    cz = _center(minz, maxz, nz, int(iz))

    out = _grid_potential_at(np.array([[cx, cy, cz]]), "deepfield")
    assert out.shape == (1,)
    assert out[0] == pytest.approx(stored, rel=1e-5)
    assert out[0] == pytest.approx(float(grid.values.min()), rel=1e-5)


def test_grid_potential_at_interior_center_equals_stored_value():
    grid = load_potential_grid("deepfield")
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape
    iz, iy, ix = 10, 20, 30
    stored = float(grid.values[iz, iy, ix])
    cx = _center(minx, maxx, nx, ix)
    cy = _center(miny, maxy, ny, iy)
    cz = _center(minz, maxz, nz, iz)
    out = _grid_potential_at(np.array([[cx, cy, cz]]), "deepfield")
    assert out[0] == pytest.approx(stored, rel=1e-5)


def test_grid_potential_at_midpoint_is_mean_of_neighbors():
    # Midpoint between two adjacent voxel centers along x -> mean of the two
    # stored values (validates real interpolation, not nearest-neighbor).
    grid = load_potential_grid("deepfield")
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape
    iz, iy, ix = 10, 20, 30
    v0 = float(grid.values[iz, iy, ix])
    v1 = float(grid.values[iz, iy, ix + 1])
    cx0 = _center(minx, maxx, nx, ix)
    cx1 = _center(minx, maxx, nx, ix + 1)
    cy = _center(miny, maxy, ny, iy)
    cz = _center(minz, maxz, nz, iz)
    mid_x = 0.5 * (cx0 + cx1)
    out = _grid_potential_at(np.array([[mid_x, cy, cz]]), "deepfield")
    assert out[0] == pytest.approx(0.5 * (v0 + v1), rel=1e-5)


def test_grid_potential_at_out_of_bounds_clamps_to_edge():
    grid = load_potential_grid("deepfield")
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape
    # y,z at the centers of the first voxel so only x drives the clamp.
    cy = _center(miny, maxy, ny, 0)
    cz = _center(minz, maxz, nz, 0)

    # Far +x clamps to the highest-ix edge voxel.
    hi = _grid_potential_at(np.array([[10_000.0, cy, cz]]), "deepfield")
    assert np.isfinite(hi[0])
    assert hi[0] == pytest.approx(float(grid.values[0, 0, nx - 1]), rel=1e-5)

    # Far -x clamps to the lowest-ix edge voxel.
    lo = _grid_potential_at(np.array([[-10_000.0, cy, cz]]), "deepfield")
    assert np.isfinite(lo[0])
    assert lo[0] == pytest.approx(float(grid.values[0, 0, 0]), rel=1e-5)


def test_grid_potential_at_clamps_to_non_corner_edge():
    # The committed sample's global min sits at corner (0,0,0); a +y clamp at a
    # genuinely interior (non-corner) x,z must hit a DISTINCT edge voxel (its
    # value differs from the global min), proving clamp picks the real nearest
    # edge rather than collapsing onto the corner.
    grid = load_potential_grid("deepfield")
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape
    ix, iz = 29, 7  # interior, non-corner
    cx = _center(minx, maxx, nx, ix)
    cz = _center(minz, maxz, nz, iz)

    edge_val = float(grid.values[iz, ny - 1, ix])
    # The +y edge voxel here is a distinct value, not the global min.
    assert edge_val != pytest.approx(float(grid.values.min()), rel=1e-5)

    out = _grid_potential_at(np.array([[cx, 1e6, cz]]), "deepfield")
    assert np.isfinite(out[0])
    assert out[0] == pytest.approx(edge_val, rel=1e-5)


def test_grid_potential_at_handles_multiple_points():
    grid = load_potential_grid("deepfield")
    pts = np.array([[0.0, 0.0, 0.0], [100.0, -50.0, 25.0], [10_000.0, 0.0, 0.0]])
    out = _grid_potential_at(pts, "deepfield")
    assert out.shape == (3,)
    assert np.all(np.isfinite(out))
