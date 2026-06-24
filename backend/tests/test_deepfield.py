"""Tests for the Deep Field potential-grid loader + trilinear interpolation.

Convention (authoritative: backend/scripts/glade/build_grid.py docstring):
- grid.npy float32 shape (nz, ny, nx), indexed grid[iz, iy, ix].
- grid.json bounds = cube FACES [minx,miny,minz,maxx,maxy,maxz]; shape [nz,ny,nx].
- Voxel CENTER along an axis [lo, hi] with n voxels:
    center(i) = lo + (i + 0.5) * (hi - lo) / n
- Axis order: pts[:,0]=x->ix, pts[:,1]=y->iy, pts[:,2]=z->iz.
"""
import json
import math

import numpy as np
import pytest

from app.services.catalog import (
    DEEPFIELD_GRID_DIR_ENV,
    load_potential_grid,
)
from app.services.physics import (
    DEEPFIELD_CALIB_RADIUS,
    MAX_WELL_DEPTH,
    _grid_potential_at,
    earth_dilation_factor,
    find_best_spot,
    find_deepest_void,
    server_dilation_factor,
)


def _center(lo: float, hi: float, n: int, i: int) -> float:
    return lo + (i + 0.5) * (hi - lo) / n


# --- Auto-derived deepfield exaggeration (Task 1) ---------------------------

def test_deepfield_exaggeration_auto_derived_hits_target(tmp_path, monkeypatch):
    from app.services.catalog import DEEPFIELD_GRID_DIR_ENV, _deepfield_grid_dir
    from app.services.physics import (
        DEEPFIELD_TARGET_ADVANTAGE,
        C_M_S,
        _deepfield_exaggeration_for,
        _grid_potential_at,
        gravitational_dilation,
    )

    # 4x4x4 grid spanning +/-100 Mpc (well inside CALIB_RADIUS=300). Uniform high
    # background potential with one clearly-deepest interior void voxel so the
    # origin interpolation (Phi_earth) stays well above Phi_void and Earth is far
    # from max_well_depth saturation (cap guard does not trigger).
    n = 4
    vals = np.full((n, n, n), 5.0e9, dtype=np.float32)
    vals[2, 2, 2] = 1.0e9  # the void (smallest potential), within 300 Mpc
    np.save(tmp_path / "grid.npy", vals)
    (tmp_path / "grid.json").write_text(json.dumps({
        "bounds": [-100.0, -100.0, -100.0, 100.0, 100.0, 100.0],
        "shape": [n, n, n],
        "unit": "Mpc",
    }))
    monkeypatch.setenv(DEEPFIELD_GRID_DIR_ENV, str(tmp_path))

    # Independent closed-form expectation, computed exactly as the helper does:
    # Phi_earth = interpolated potential at origin; Phi_void = min within ball.
    k = 2.0 / C_M_S ** 2
    phi_earth = float(_grid_potential_at(np.array([[0.0, 0.0, 0.0]]), "deepfield")[0])
    phi_void = float(vals.min())  # whole grid is within 300 Mpc -> global min
    a2 = DEEPFIELD_TARGET_ADVANTAGE ** 2
    expected_ex = (a2 - 1.0) / (k * (a2 * phi_earth - phi_void))

    # Sanity: Earth must be well under the saturation cap so the guard is inert.
    assert expected_ex * k * phi_earth < 0.9 * 0.7

    ex = _deepfield_exaggeration_for(_deepfield_grid_dir())
    assert ex == pytest.approx(expected_ex, rel=1e-6)

    # Feeding the void's Phi through dilation reproduces the target advantage.
    f_void = gravitational_dilation(phi_void, "deepfield")
    f_earth = gravitational_dilation(phi_earth, "deepfield")
    assert f_void / f_earth == pytest.approx(DEEPFIELD_TARGET_ADVANTAGE, rel=1e-3)


def test_deepfield_advantage_grid_independent_no_saturation(tmp_path, monkeypatch):
    # Regression for the original production bug: pointing the backend at a
    # DENSER grid (potentials ~100x the committed sample's, mimicking the full
    # catalog) used to saturate max_well_depth=0.7 at BOTH Earth and the void
    # with the old hardcoded DEEPFIELD_EXAGGERATION=8e5 -> both factors pinned at
    # sqrt(0.3) and clock_advantage collapsed to ~1.0. Tasks 1-2 (auto-derived
    # per-grid exaggeration + grid-dir-keyed Earth-factor cache) self-calibrate
    # any grid to the teaching band with Earth NOT saturated.
    #
    # On main (8e5 * k * Phi with Phi~1e12 => ex*2Phi/c^2 >> 0.7) BOTH Earth and
    # void clamp to sqrt(1-0.7)=sqrt(0.3)~0.5477 and adv ~= 1.0 < 1.05: this test
    # would FAIL there. Tasks 1-2 make it pass.
    #
    # Geometry: 8x8x8 cube spanning +-500 Mpc (real bounds). Uniformly high
    # background (~100x the sample, so Earth at the origin interpolates to a large
    # Phi and stays dense) with one clearly-deepest interior void voxel inside the
    # 300 Mpc calibration ball. Voxel center along [-500, 500] with 8 voxels:
    # center(i) = -500 + (i + 0.5) * 1000 / 8. center(4) = 62.5, so voxel
    # [4, 4, 4] sits at (62.5, 62.5, 62.5), |r| ~= 108 Mpc -- inside the calib ball
    # and away from the origin (origin's x-bracket is ix in {3, 4}).
    n = 8
    vals = np.full((n, n, n), 8.0e11, dtype=np.float32)  # dense background (~100x)
    vals[4, 4, 4] = 5.0e9  # the void: clear interior minimum, within 300 Mpc
    np.save(tmp_path / "grid.npy", vals)
    (tmp_path / "grid.json").write_text(json.dumps({
        "bounds": [-500.0, -500.0, -500.0, 500.0, 500.0, 500.0],
        "shape": [n, n, n],
        "unit": "Mpc",
    }))
    monkeypatch.setenv(DEEPFIELD_GRID_DIR_ENV, str(tmp_path))

    # The deepest-void advantage self-calibrates to the teaching band (~1.06).
    pt = find_deepest_void(DEEPFIELD_CALIB_RADIUS, scale="deepfield")
    adv = (
        server_dilation_factor(pt["x"], pt["y"], pt["z"], "deepfield")
        / earth_dilation_factor("deepfield")
    )
    assert 1.05 <= adv <= 1.10

    # The crux: Earth must NOT be saturated at the max_well_depth floor. This is
    # exactly what the bug violated (both factors pinned at sqrt(0.3)).
    floor = math.sqrt(1 - MAX_WELL_DEPTH)  # sqrt(0.3) ~= 0.5477
    assert earth_dilation_factor("deepfield") > floor + 1e-3


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


# --- Grid-based void / best-spot search (Task 2C.3) -------------------------
# The deepfield branch reads the cached potential grid (no catalog), restricts
# voxel centers to the latency-budget ball, and returns the argmin-potential /
# argmax-net voxel center. O(voxels), vectorized, deterministic.

DEEPFIELD_SEARCH_R = 300.0  # Mpc latency-budget radius for deepfield searches


def _r_max() -> float:
    """The committed sample's cube half-extent (Mpc)."""
    minx, miny, minz, maxx, maxy, maxz = load_potential_grid("deepfield").bounds
    return max(maxx, maxy, maxz)


def test_find_deepest_void_deepfield_inside_cube_and_beats_earth():
    pt = find_deepest_void(DEEPFIELD_SEARCH_R, scale="deepfield")
    r = _r_max()
    # Inside the ±R_MAX cube.
    assert -r <= pt["x"] <= r
    assert -r <= pt["y"] <= r
    assert -r <= pt["z"] <= r
    # Inside the latency-budget ball.
    d = (pt["x"] ** 2 + pt["y"] ** 2 + pt["z"] ** 2) ** 0.5
    assert d <= DEEPFIELD_SEARCH_R + 1e-6
    # The server's clock there beats Earth's.
    f_server = server_dilation_factor(pt["x"], pt["y"], pt["z"], "deepfield")
    f_earth = earth_dilation_factor("deepfield")
    assert f_server / f_earth > 1.0


def test_find_deepest_void_deepfield_advantage_in_calibrated_band():
    # Final calibration (Task 2D.1): the deepest-void clock advantage must land
    # in the tight 1.05-1.10 target band (DEEPFIELD_EXAGGERATION = 8.0e5 -> ~1.060).
    pt = find_deepest_void(DEEPFIELD_SEARCH_R, scale="deepfield")
    f_server = server_dilation_factor(pt["x"], pt["y"], pt["z"], "deepfield")
    f_earth = earth_dilation_factor("deepfield")
    adv = f_server / f_earth
    assert 1.05 <= adv <= 1.10


def test_find_deepest_void_deepfield_deterministic():
    a = find_deepest_void(DEEPFIELD_SEARCH_R, scale="deepfield")
    b = find_deepest_void(DEEPFIELD_SEARCH_R, scale="deepfield")
    assert a == b


def test_find_deepest_void_deepfield_returns_voxel_center():
    # The result must be an actual voxel center, not an interpolated point.
    grid = load_potential_grid("deepfield")
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape
    pt = find_deepest_void(DEEPFIELD_SEARCH_R, scale="deepfield")

    def _is_center(v, lo, hi, n):
        # v == lo + (i + 0.5) * (hi - lo) / n for some integer i in [0, n).
        i = (v - lo) / (hi - lo) * n - 0.5
        return abs(i - round(i)) < 1e-6 and 0 <= round(i) < n

    assert _is_center(pt["x"], minx, maxx, nx)
    assert _is_center(pt["y"], miny, maxy, ny)
    assert _is_center(pt["z"], minz, maxz, nz)


def test_find_best_spot_deepfield_finite_positive_net():
    # At cosmic distances round-trip light latency is enormous (~10^15 s even
    # for the nearest voxel), so the task must be large enough to clear the
    # latency breakeven before any net gain appears.
    huge_task = 1e19  # seconds
    pt = find_best_spot(huge_task, DEEPFIELD_SEARCH_R, scale="deepfield")
    assert np.isfinite(pt["x"]) and np.isfinite(pt["y"]) and np.isfinite(pt["z"])
    r = _r_max()
    assert -r <= pt["x"] <= r and -r <= pt["y"] <= r and -r <= pt["z"] <= r

    # Net gain at the chosen spot is positive for a huge task.
    from app.services.physics import C, MPC_KM, compute_efficiency

    f_earth = earth_dilation_factor("deepfield")
    f_server = server_dilation_factor(pt["x"], pt["y"], pt["z"], "deepfield")
    d = (pt["x"] ** 2 + pt["y"] ** 2 + pt["z"] ** 2) ** 0.5
    latency = (2 * d * MPC_KM) / C
    eff = compute_efficiency(huge_task, f_earth, f_server, latency)
    assert eff["net_gain"] > 0


def test_find_best_spot_deepfield_deterministic():
    huge_task = 1e19
    a = find_best_spot(huge_task, DEEPFIELD_SEARCH_R, scale="deepfield")
    b = find_best_spot(huge_task, DEEPFIELD_SEARCH_R, scale="deepfield")
    assert a == b


def _nearest_voxel_center_to_origin():
    """The voxel center closest to the origin (the empty-ball fallback target)."""
    grid = load_potential_grid("deepfield")
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape

    def centers(lo, hi, n):
        return lo + (np.arange(n) + 0.5) * (hi - lo) / n

    cx, cy, cz = centers(minx, maxx, nx), centers(miny, maxy, ny), centers(minz, maxz, nz)
    zz, yy, xx = np.meshgrid(cz, cy, cx, indexing="ij")
    pts = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    return pts[int(np.argmin((pts ** 2).sum(axis=1)))]


def test_find_deepest_void_deepfield_empty_ball_falls_back_to_nearest():
    # radius 0 -> no voxel center is within the ball; must fall back to the
    # nearest voxel center to origin (finite, real voxel), not crash/return empty.
    pt = find_deepest_void(0.0, scale="deepfield")
    assert np.isfinite(pt["x"]) and np.isfinite(pt["y"]) and np.isfinite(pt["z"])
    nearest = _nearest_voxel_center_to_origin()
    assert (pt["x"], pt["y"], pt["z"]) == (nearest[0], nearest[1], nearest[2])


def test_find_best_spot_deepfield_empty_ball_falls_back_to_nearest():
    pt = find_best_spot(1e19, 0.0, scale="deepfield")
    assert np.isfinite(pt["x"]) and np.isfinite(pt["y"]) and np.isfinite(pt["z"])
    nearest = _nearest_voxel_center_to_origin()
    assert (pt["x"], pt["y"], pt["z"]) == (nearest[0], nearest[1], nearest[2])


# --- Regression: solar + cosmic paths unchanged ----------------------------
# Known values captured BEFORE the 2C.3 change. A deepfield change must not
# alter the catalog-based searches.

_SOLAR_VOID = {"x": -66.66666666666669, "y": 33.33333333333326, "z": 66.66666666666657}
_COSMIC_VOID = {"x": 39.66666666666657, "y": -85.33333333333334, "z": 33.83333333333326}
_BEST_ORIGIN = {
    "x": -5.684341886080802e-14,
    "y": -5.684341886080802e-14,
    "z": -5.684341886080802e-14,
}


@pytest.mark.parametrize(
    "scale, expected_void, expected_best",
    [
        ("solar", _SOLAR_VOID, _BEST_ORIGIN),
        ("cosmic", _COSMIC_VOID, _BEST_ORIGIN),
    ],
)
def test_catalog_searches_unchanged(scale, expected_void, expected_best):
    assert find_deepest_void(100.0, scale=scale) == expected_void
    assert find_best_spot(1e9, 100.0, scale=scale) == expected_best


# --- Deepfield API surface (Task 2D.1) --------------------------------------
# Exercise the real FastAPI router end-to-end via TestClient: the deepfield
# scale must flow through the schema Literal and produce finite grid-backed
# physics. No /api/galaxies-style JSON exists for deepfield — galaxies are
# tiles; the API only does physics via the grid.

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_efficiency_deepfield_returns_finite_metrics():
    # A sample void-ish point inside the ±500 Mpc cube; huge task to clear the
    # enormous cosmological round-trip latency.
    payload = {
        "x": -93.75,
        "y": -31.25,
        "z": -281.25,
        "task_seconds": 1e19,
        "scale": "deepfield",
    }
    resp = client.post("/api/physics/efficiency", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    for field in (
        "earth_compute_time",
        "earth_wait_time",
        "net_gain",
        "latency_seconds",
        "earth_dilation_factor",
        "server_dilation_factor",
        "clock_advantage",
        "breakeven_task_seconds",
    ):
        assert field in data
        assert np.isfinite(data[field]), f"{field} not finite: {data[field]!r}"
    # Grid-backed dilation factors are physical, server beats Earth in the void.
    assert 0.0 < data["earth_dilation_factor"] <= 1.0
    assert 0.0 < data["server_dilation_factor"] <= 1.0
    assert data["clock_advantage"] > 1.0


def test_api_best_void_deepfield_finite_coords_in_cube():
    payload = {"max_distance_pc": DEEPFIELD_SEARCH_R, "scale": "deepfield"}
    resp = client.post("/api/physics/best-void", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    for axis in ("x", "y", "z"):
        assert np.isfinite(data[axis])
        assert -500.0 <= data[axis] <= 500.0


def test_api_best_spot_deepfield_finite_coords_in_cube():
    payload = {
        "task_seconds": 1e19,
        "max_distance_pc": DEEPFIELD_SEARCH_R,
        "scale": "deepfield",
    }
    resp = client.post("/api/physics/best-spot", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    for axis in ("x", "y", "z"):
        assert np.isfinite(data[axis])
        assert -500.0 <= data[axis] <= 500.0


def test_api_schema_accepts_deepfield_rejects_bad_scale():
    # The new Literal accepts "deepfield" ...
    ok = client.post(
        "/api/physics/best-void",
        json={"max_distance_pc": DEEPFIELD_SEARCH_R, "scale": "deepfield"},
    )
    assert ok.status_code == 200
    # ... but an unknown scale is a 422 validation error.
    bad = client.post(
        "/api/physics/best-void",
        json={"max_distance_pc": DEEPFIELD_SEARCH_R, "scale": "nope"},
    )
    assert bad.status_code == 422


def test_earth_dilation_factor_deepfield_finite_in_unit_interval():
    fe = earth_dilation_factor("deepfield")
    assert np.isfinite(fe)
    assert 0.0 < fe <= 1.0
