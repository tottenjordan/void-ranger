import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import numpy as np

from app.services.catalog import (
    _deepfield_grid_dir,
    _load_grid,
    load_galaxy_arrays,
    load_potential_grid,
    load_star_arrays,
)

C = 299_792.458          # speed of light in km/s
C_M_S = C * 1000         # speed of light in m/s
G = 6.674e-11            # gravitational constant (m^3 kg^-1 s^-2)
PARSEC_KM = 3.086e13     # km per parsec
PARSEC_M = 3.086e16      # m per parsec
MPC_KM = 3.086e19        # km per megaparsec
MPC_M = 3.086e22         # m per megaparsec

# --- Gravitational dilation model -------------------------------------------
# Both Earth and the server sit in the same field of catalog masses. We use the
# weak-field metric: a clock at gravitational potential Phi ticks at rate
# sqrt(1 + 2*Phi/c^2) relative to flat spacetime (Phi < 0, so the factor < 1).
# Real interstellar/cosmic potentials are tiny — invisible — so we apply a
# documented EXAGGERATION so that the dense solar neighborhood vs. deep voids
# produce a visible (few-to-tens-of-percent) spread. A softening length keeps
# the potential finite when a server is placed right on top of a mass.
SOFTENING_M = 0.1 * PARSEC_M
GRAVITY_EXAGGERATION = 5.5e9
MAX_WELL_DEPTH = 0.7     # cap so the dilation factor stays real and sane

# Cosmic exaggeration, calibrated so the deepest void within 100 Mpc gives a
# clock_advantage of ~1.05 over Earth (a visible but modest edge, in the target
# 1.03-1.10 band). Real void-vs-supercluster potential differences are
# minuscule. Calibration sweep (find_deepest_void(100, scale="cosmic")):
#   exa=8e4 -> adv 1.036,  exa=1.0e5 -> adv 1.049,  exa=1.2e5 -> adv 1.066.
# Above ~5e5 both Earth and the void saturate max_well_depth and the advantage
# collapses to ~1.0, so the value must stay in this lower window.
COSMIC_EXAGGERATION = 1.0e5

# Deepfield exaggeration is AUTO-DERIVED per grid (see _deepfield_exaggeration_for)
# rather than hardcoded, because the deepfield scale reads RAW potential (J/kg)
# from a precomputed grid whose magnitude scales with catalog density. A single
# constant calibrated on one grid saturates max_well_depth on a denser grid and
# the advantage collapses to ~1.0. Instead we expose an intuitive TARGET advantage
# and solve for the exaggeration that puts the deepest void within CALIB_RADIUS at
# exactly that advantage, for ANY grid.
#
# exaggeration is a LABELED TEACHING DEVICE: real cosmic dilation is ~1 part in
# 10^13 (invisible). It multiplies 2Φ/c² so the void-vs-dense contrast becomes a
# visible few percent. It does NOT move the void (that's the raw-potential argmin,
# exaggeration-independent) — only the reported advantage and find_best_spot's
# trade-off. Implications of the value:
#   too low  -> advantage ≈ 1.000 (effect invisible, no teaching signal)
#   in band  -> advantage ~1.05-1.10 (visible, modest, honest about contrast)
#   too high -> 2Φ/c²·ex exceeds max_well_depth at BOTH Earth and void -> both
#               saturate at √0.3 -> advantage collapses back to 1.0
DEEPFIELD_TARGET_ADVANTAGE = 1.06   # teaching-band center; the tunable knob
DEEPFIELD_CALIB_RADIUS = 300.0      # Mpc; matches the UI/search radius so calib
                                    # uses the same deepest void the app surfaces


@dataclass(frozen=True)
class ScaleConfig:
    """Per-scale physical constants and catalog loader.

    length_m / length_km convert catalog coordinates (parsecs for solar,
    megaparsecs for cosmic) to meters / km. softening_m keeps the potential
    finite. exaggeration / max_well_depth shape the (teaching) dilation spread.
    exaggeration is None for grid-backed scales (deepfield), which auto-derive
    it per grid via _effective_exaggeration / _deepfield_exaggeration_for.
    load() returns (xs, ys, zs, masses_kg) for the scale's catalog.
    """

    length_m: float
    length_km: float
    softening_m: float
    # Teaching exaggeration factor; None = auto-derived per grid for grid-backed
    # scales (deepfield). Use _effective_exaggeration(scale) to resolve it.
    exaggeration: float | None
    max_well_depth: float
    # Catalog loader -> (xs, ys, zs, masses_kg). None for grid-backed scales
    # (deepfield), which read a precomputed potential grid instead of a catalog.
    load: Callable[[], tuple] | None


SCALES: dict[str, ScaleConfig] = {
    "solar": ScaleConfig(
        length_m=PARSEC_M,
        length_km=PARSEC_KM,
        softening_m=0.1 * PARSEC_M,
        exaggeration=GRAVITY_EXAGGERATION,
        max_well_depth=MAX_WELL_DEPTH,
        load=load_star_arrays,
    ),
    "cosmic": ScaleConfig(
        length_m=MPC_M,
        length_km=MPC_KM,
        softening_m=0.5 * MPC_M,
        exaggeration=COSMIC_EXAGGERATION,
        max_well_depth=MAX_WELL_DEPTH,
        load=load_galaxy_arrays,
    ),
    # Grid-backed scale: local_potential / searches read load_potential_grid
    # instead of a catalog, so load is None (nothing should call it here).
    "deepfield": ScaleConfig(
        length_m=MPC_M,
        length_km=MPC_KM,
        softening_m=0.5 * MPC_M,
        exaggeration=None,  # auto-derived per grid (see _effective_exaggeration)
        max_well_depth=MAX_WELL_DEPTH,
        load=None,
    ),
}


def _scale(scale: str) -> ScaleConfig:
    try:
        return SCALES[scale]
    except KeyError:
        raise ValueError(f"unknown scale: {scale!r}")


def galactic_to_cartesian(d: float, l: float, b: float) -> dict:
    l_rad = math.radians(l)
    b_rad = math.radians(b)
    return {
        "x": d * math.cos(b_rad) * math.cos(l_rad),
        "y": d * math.cos(b_rad) * math.sin(l_rad),
        "z": d * math.sin(b_rad),
    }


def light_latency(x: float, y: float, z: float, scale: str = "solar") -> float:
    """Round-trip light-speed latency from Earth (0,0,0) to (x,y,z).

    Coordinates are in the scale's length unit (parsecs for solar, megaparsecs
    for cosmic).
    """
    cfg = _scale(scale)
    dist = math.sqrt(x**2 + y**2 + z**2)
    dist_km = dist * cfg.length_km
    return (2 * dist_km) / C


def local_potential(x: float, y: float, z: float, scale: str = "solar") -> float:
    """Newtonian gravitational potential magnitude at (x,y,z).

    Coordinates are in the scale's length unit. Returns sum of G*M_i / r_eff
    over all catalog masses (J/kg, positive), with softening to avoid
    singularities. Larger = deeper in the field.
    """
    cfg = _scale(scale)
    if cfg.load is None:
        # Grid-backed scale (deepfield): read the precomputed potential grid.
        return float(_grid_potential_at(np.array([[x, y, z]]), scale)[0])
    xs, ys, zs, masses_kg = cfg.load()
    dx = (x - xs) * cfg.length_m
    dy = (y - ys) * cfg.length_m
    dz = (z - zs) * cfg.length_m
    r = np.sqrt(dx * dx + dy * dy + dz * dz + cfg.softening_m ** 2)
    return float(np.sum(G * masses_kg / r))


def gravitational_dilation(potential: float, scale: str = "solar") -> float:
    """Clock-rate factor (< 1) for a clock at the given potential magnitude.

    Returns dτ/dt relative to flat spacetime; 1.0 in a perfect void, smaller
    deeper in the gravitational field.
    """
    cfg = _scale(scale)
    ex = _effective_exaggeration(scale)
    depth = min(ex * 2 * potential / C_M_S ** 2, cfg.max_well_depth)
    return math.sqrt(1 - depth)


@lru_cache(maxsize=None)
def _catalog_earth_factor(scale: str) -> float:
    return gravitational_dilation(local_potential(0.0, 0.0, 0.0, scale), scale)


@lru_cache(maxsize=4)
def _deepfield_earth_factor(grid_dir) -> float:
    return gravitational_dilation(local_potential(0.0, 0.0, 0.0, "deepfield"), "deepfield")


def earth_dilation_factor(scale: str = "solar") -> float:
    """Earth's clock factor: it sits at the origin, deep in the dense
    neighborhood, so its clock runs slow relative to a distant void.

    Cached per scale for catalog scales; for the grid-backed deepfield scale the
    cache is keyed on the resolved grid directory so a DEEPFIELD_GRID_DIR
    override (e.g. swapping to the full-catalog grid) recomputes rather than
    serving the first grid's stale Earth factor.
    """
    if _scale(scale).load is None:
        return _deepfield_earth_factor(_deepfield_grid_dir())
    return _catalog_earth_factor(scale)


def server_dilation_factor(x: float, y: float, z: float, scale: str = "solar") -> float:
    """The void server's clock factor, from the local potential at its position."""
    return gravitational_dilation(local_potential(x, y, z, scale), scale)


def compute_efficiency(task_seconds: float, f_earth: float, f_server: float,
                       latency_seconds: float) -> dict:
    """Efficiency of offloading a task to the server.

    The server completes the task in task_seconds of its own proper time. The
    Earth time that elapses meanwhile is task_seconds * (f_earth / f_server):
    when the server's clock is faster (f_server > f_earth, i.e. it sits in a
    weaker field) Earth ages less, so the work effectively finishes sooner.
    """
    earth_compute_time = task_seconds * (f_earth / f_server)
    earth_wait_time = earth_compute_time + latency_seconds
    net_gain = task_seconds - earth_wait_time
    return {
        "earth_compute_time": earth_compute_time,
        "earth_wait_time": earth_wait_time,
        "net_gain": net_gain,
    }


def breakeven_task_seconds(f_earth: float, f_server: float,
                           latency_seconds: float) -> float | None:
    """Smallest task (in server proper-seconds) whose dilation savings just
    cover the round-trip light delay. Returns None when the server is not in a
    weaker field than Earth (f_server <= f_earth), i.e. no task size ever wins.
    """
    ratio = f_earth / f_server
    if ratio >= 1:
        return None
    return latency_seconds / (1 - ratio)


# --- Placement search (deepest void / best spot) ----------------------------
# Both searches scan candidate points inside a ball of radius max_distance_pc
# (the distance cap is a LATENCY budget, not a gravity assumption) and evaluate
# the full catalog potential at each — so they account for proximity to *every*
# star, not distance from Earth. A coarse grid finds the basin; two levels of
# local refinement polish it. Deterministic (fixed grid, no RNG).

def _ball_points(max_distance_pc: float, step: float) -> np.ndarray:
    """Deterministic grid points (parsecs) inside the ball of the given radius."""
    axis = np.arange(-max_distance_pc, max_distance_pc + step, step)
    gx, gy, gz = np.meshgrid(axis, axis, axis, indexing="ij")
    pts = np.column_stack([gx.ravel(), gy.ravel(), gz.ravel()])
    return pts[(pts ** 2).sum(axis=1) <= max_distance_pc ** 2]


def _potential_at(pts: np.ndarray, scale: str = "solar") -> np.ndarray:
    """Vectorized gravitational potential (J/kg) at each row of pts.

    Coordinates are in the scale's length unit. Chunked over candidates to bound
    memory (~chunk x n_masses at a time).
    """
    cfg = _scale(scale)
    xs, ys, zs, masses_kg = cfg.load()
    sx, sy, sz = xs * cfg.length_m, ys * cfg.length_m, zs * cfg.length_m
    out = np.empty(len(pts))
    CHUNK = 256
    for i in range(0, len(pts), CHUNK):
        c = pts[i:i + CHUNK] * cfg.length_m
        dx = c[:, 0:1] - sx[None, :]
        dy = c[:, 1:2] - sy[None, :]
        dz = c[:, 2:3] - sz[None, :]
        r = np.sqrt(dx * dx + dy * dy + dz * dz + cfg.softening_m ** 2)
        out[i:i + len(c)] = np.sum(G * masses_kg[None, :] / r, axis=1)
    return out


def _grid_potential_at(pts: np.ndarray, scale: str = "deepfield") -> np.ndarray:
    """Trilinearly-interpolated potential (J/kg) at each point, from the grid.

    pts is (N, 3) in Mpc (a single (3,) is accepted too): pts[:,0]=x->ix,
    pts[:,1]=y->iy, pts[:,2]=z->iz, indexing grid[iz, iy, ix]. Each coordinate
    maps to a fractional VOXEL-CENTER index along its axis,

        center(i) = lo + (i + 0.5) * (hi - lo) / n
        => frac    = (coord - lo) / (hi - lo) * n - 0.5

    and we interpolate among the 8 surrounding voxel centers. The fractional
    index is clamped to [0, n-1], so points outside the cube (or in the
    half-voxel margin past the outermost centers) take the nearest edge voxel
    value — no extrapolation, no NaN. Replaces the catalog-sum potential for the
    deepfield scale.
    """
    grid = load_potential_grid(scale)
    values = grid.values
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape

    pts = np.atleast_2d(np.asarray(pts, dtype=np.float64))

    def _frac_index(coord: np.ndarray, lo: float, hi: float, n: int) -> np.ndarray:
        f = (coord - lo) / (hi - lo) * n - 0.5
        return np.clip(f, 0.0, n - 1)

    fx = _frac_index(pts[:, 0], minx, maxx, nx)
    fy = _frac_index(pts[:, 1], miny, maxy, ny)
    fz = _frac_index(pts[:, 2], minz, maxz, nz)

    ix0 = np.clip(np.floor(fx).astype(int), 0, nx - 1)
    iy0 = np.clip(np.floor(fy).astype(int), 0, ny - 1)
    iz0 = np.clip(np.floor(fz).astype(int), 0, nz - 1)
    ix1 = np.minimum(ix0 + 1, nx - 1)
    iy1 = np.minimum(iy0 + 1, ny - 1)
    iz1 = np.minimum(iz0 + 1, nz - 1)

    tx = fx - ix0
    ty = fy - iy0
    tz = fz - iz0

    vals = values.astype(np.float64)

    # Trilinear blend over the 8 corners (grid indexed [iz, iy, ix]).
    c000 = vals[iz0, iy0, ix0]
    c001 = vals[iz0, iy0, ix1]
    c010 = vals[iz0, iy1, ix0]
    c011 = vals[iz0, iy1, ix1]
    c100 = vals[iz1, iy0, ix0]
    c101 = vals[iz1, iy0, ix1]
    c110 = vals[iz1, iy1, ix0]
    c111 = vals[iz1, iy1, ix1]

    c00 = c000 * (1 - tx) + c001 * tx
    c01 = c010 * (1 - tx) + c011 * tx
    c10 = c100 * (1 - tx) + c101 * tx
    c11 = c110 * (1 - tx) + c111 * tx

    c0 = c00 * (1 - ty) + c01 * ty
    c1 = c10 * (1 - ty) + c11 * ty

    return c0 * (1 - tz) + c1 * tz


@lru_cache(maxsize=4)
def _voxel_centers_for(grid_dir) -> tuple[np.ndarray, np.ndarray]:
    """Cached (centers, values) for the grid in a resolved directory.

    Keyed on the resolved grid_dir (not the scale string) so a
    DEEPFIELD_GRID_DIR override yields fresh centers — mirroring catalog's
    _load_grid. centers is (n_voxels, 3) in Mpc (x, y, z) and values is
    (n_voxels,) of the stored potential magnitude (J/kg), aligned row-for-row.
    """
    grid = _load_grid(grid_dir)
    minx, miny, minz, maxx, maxy, maxz = grid.bounds
    nz, ny, nx = grid.shape

    def _centers(lo: float, hi: float, n: int) -> np.ndarray:
        return lo + (np.arange(n) + 0.5) * (hi - lo) / n

    cx = _centers(minx, maxx, nx)
    cy = _centers(miny, maxy, ny)
    cz = _centers(minz, maxz, nz)
    # grid indexed [iz, iy, ix]; match the flatten order of values.ravel().
    zz, yy, xx = np.meshgrid(cz, cy, cx, indexing="ij")
    centers = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    values = np.asarray(grid.values, dtype=np.float64).ravel()
    return centers, values


@lru_cache(maxsize=4)
def _deepfield_exaggeration_for(grid_dir) -> float:
    """Auto-derived deepfield exaggeration for the grid in a resolved directory.

    Closed form: with f = √(1 − ex·k·Φ), k = 2/c², solving
    A = f_void/f_earth for ex gives ex = (A²−1)/(k·(A²·Φ_earth − Φ_void)).
    Φ_earth is the interpolated potential at the origin; Φ_void is the minimum
    voxel potential within DEEPFIELD_CALIB_RADIUS. By construction the deepest
    void within that radius has clock advantage DEEPFIELD_TARGET_ADVANTAGE for
    ANY grid, with no max_well_depth saturation. Keyed on grid_dir (mirroring
    _voxel_centers_for / catalog._load_grid) so a DEEPFIELD_GRID_DIR override
    derives fresh.
    """
    centers, values = _voxel_centers_for(grid_dir)
    k = 2.0 / C_M_S ** 2
    phi_earth = float(_grid_potential_at(np.array([[0.0, 0.0, 0.0]]), "deepfield")[0])
    d2 = (centers ** 2).sum(axis=1)
    in_ball = d2 <= DEEPFIELD_CALIB_RADIUS ** 2
    phi_void = float(values[in_ball].min()) if in_ball.any() else float(values.min())
    a2 = DEEPFIELD_TARGET_ADVANTAGE ** 2
    denom = k * (a2 * phi_earth - phi_void)
    ex = (a2 - 1.0) / denom if denom > 0 else 0.0
    # Guard the degenerate "no real void" grid: keep Earth's own depth
    # (ex·k·Φ_earth) under the max_well_depth clamp so Earth never saturates.
    cap = (0.9 * MAX_WELL_DEPTH) / (k * phi_earth) if phi_earth > 0 else ex
    return min(ex, cap)


def _effective_exaggeration(scale: str) -> float:
    """The exaggeration to use for a scale: the configured constant for catalog
    scales, or the grid-auto-derived value for grid-backed deepfield (sentinel
    exaggeration=None)."""
    cfg = _scale(scale)
    if cfg.exaggeration is not None:
        return cfg.exaggeration
    return _deepfield_exaggeration_for(_deepfield_grid_dir())


def _grid_voxel_centers(scale: str = "deepfield") -> tuple[np.ndarray, np.ndarray]:
    """(centers, values) for a grid scale, flattened over voxels.

    Resolves the grid directory here (so a DEEPFIELD_GRID_DIR env change is
    honored) and delegates to a cache keyed on that directory — the same pattern
    as catalog.load_potential_grid. Built once per grid so the O(voxels)
    searches don't rebuild the coordinate arrays per call.
    """
    if scale != "deepfield":
        raise ValueError(f"no potential grid for scale: {scale!r}")
    return _voxel_centers_for(_deepfield_grid_dir())


def _dilation_array(potential: np.ndarray, scale: str = "solar") -> np.ndarray:
    """Vectorized clock factor for an array of potential magnitudes."""
    cfg = _scale(scale)
    ex = _effective_exaggeration(scale)
    depth = np.minimum(ex * 2 * potential / C_M_S ** 2, cfg.max_well_depth)
    return np.sqrt(1 - depth)


def _refine(best: np.ndarray, pick, max_distance_pc: float, span: float) -> np.ndarray:
    """Two levels of local grid refinement around `best`.

    `pick(local_points) -> index` selects the winner (argmin/argmax of the objective).
    """
    for _ in range(2):
        span /= 5.0
        axis = np.linspace(-span, span, 5)
        gx, gy, gz = np.meshgrid(axis, axis, axis, indexing="ij")
        local = best + np.column_stack([gx.ravel(), gy.ravel(), gz.ravel()])
        local = local[(local ** 2).sum(axis=1) <= max_distance_pc ** 2]
        if len(local) == 0:
            break
        best = local[pick(local)]
    return best


def find_deepest_void(max_distance_pc: float = 300.0, scale: str = "solar") -> dict:
    """Coordinates of the lowest-potential point within max_distance_pc.

    max_distance_pc is the search radius in the scale's length unit (parsecs for
    solar, megaparsecs for cosmic). Minimizes the full catalog potential, i.e.
    the point farthest from *all* massive bodies (an empty pocket) — not the
    point farthest from Earth.

    Deepfield is grid-backed: it scans the grid's voxel centers within the
    latency-budget ball and returns the argmin-potential center. O(voxels),
    independent of catalog size.
    """
    if _scale(scale).load is None:
        centers, values = _grid_voxel_centers(scale)
        d2 = (centers ** 2).sum(axis=1)
        mask = d2 <= max_distance_pc ** 2
        if not mask.any():
            # No voxel inside the radius; fall back to the nearest voxel center.
            mask = np.zeros(len(centers), dtype=bool)
            mask[int(np.argmin(d2))] = True
        idx = np.flatnonzero(mask)
        best = centers[idx[int(np.argmin(values[idx]))]]
        return {"x": float(best[0]), "y": float(best[1]), "z": float(best[2])}

    step = max_distance_pc / 12.0
    pts = _ball_points(max_distance_pc, step)
    best = pts[int(np.argmin(_potential_at(pts, scale)))]
    best = _refine(best, lambda L: int(np.argmin(_potential_at(L, scale))), max_distance_pc, step)
    return {"x": float(best[0]), "y": float(best[1]), "z": float(best[2])}


def find_best_spot(task_seconds: float, max_distance_pc: float = 300.0,
                   scale: str = "solar") -> dict:
    """Coordinates within max_distance_pc that maximize net gain for a task.

    max_distance_pc is the search radius in the scale's length unit.
    net_gain = task * (1 - f_earth/f_server) - latency; balances the void's clock
    advantage against round-trip light latency.

    Deepfield is grid-backed: per voxel center within the latency-budget ball it
    computes net = task*(1 - f_earth/f_server) - 2d/c and returns the argmax-net
    center. O(voxels), independent of catalog size.
    """
    cfg = _scale(scale)
    f_earth = earth_dilation_factor(scale)

    if cfg.load is None:
        centers, values = _grid_voxel_centers(scale)
        d = np.sqrt((centers ** 2).sum(axis=1))
        mask = d <= max_distance_pc
        if not mask.any():
            mask = np.zeros(len(centers), dtype=bool)
            mask[int(np.argmin(d))] = True
        idx = np.flatnonzero(mask)
        f_server = _dilation_array(values[idx], scale)
        latency = (2 * d[idx] * cfg.length_km) / C
        net_gain = task_seconds * (1 - f_earth / f_server) - latency
        best = centers[idx[int(np.argmax(net_gain))]]
        return {"x": float(best[0]), "y": float(best[1]), "z": float(best[2])}

    def net(pts: np.ndarray) -> np.ndarray:
        f_server = _dilation_array(_potential_at(pts, scale), scale)
        d = np.sqrt((pts ** 2).sum(axis=1))
        latency = (2 * d * cfg.length_km) / C
        return task_seconds * (1 - f_earth / f_server) - latency

    step = max_distance_pc / 12.0
    pts = _ball_points(max_distance_pc, step)
    best = pts[int(np.argmax(net(pts)))]
    best = _refine(best, lambda L: int(np.argmax(net(L))), max_distance_pc, step)
    return {"x": float(best[0]), "y": float(best[1]), "z": float(best[2])}
