import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import numpy as np

from app.services.catalog import load_galaxy_arrays, load_star_arrays

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


@dataclass(frozen=True)
class ScaleConfig:
    """Per-scale physical constants and catalog loader.

    length_m / length_km convert catalog coordinates (parsecs for solar,
    megaparsecs for cosmic) to meters / km. softening_m keeps the potential
    finite. exaggeration / max_well_depth shape the (teaching) dilation spread.
    load() returns (xs, ys, zs, masses_kg) for the scale's catalog.
    """

    length_m: float
    length_km: float
    softening_m: float
    exaggeration: float
    max_well_depth: float
    load: Callable[[], tuple]


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
    depth = min(cfg.exaggeration * 2 * potential / C_M_S ** 2, cfg.max_well_depth)
    return math.sqrt(1 - depth)


@lru_cache(maxsize=None)
def earth_dilation_factor(scale: str = "solar") -> float:
    """Earth's clock factor: it sits at the origin, deep in the dense
    neighborhood, so its clock runs slow relative to a distant void.

    Cached per scale (the cache key includes the scale argument).
    """
    return gravitational_dilation(local_potential(0.0, 0.0, 0.0, scale), scale)


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


def _dilation_array(potential: np.ndarray, scale: str = "solar") -> np.ndarray:
    """Vectorized clock factor for an array of potential magnitudes."""
    cfg = _scale(scale)
    depth = np.minimum(cfg.exaggeration * 2 * potential / C_M_S ** 2, cfg.max_well_depth)
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
    """
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
    """
    cfg = _scale(scale)
    f_earth = earth_dilation_factor(scale)

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
