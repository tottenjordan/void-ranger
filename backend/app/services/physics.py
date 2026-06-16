import math
from functools import lru_cache

import numpy as np

from app.services.catalog import load_star_arrays

C = 299_792.458          # speed of light in km/s
C_M_S = C * 1000         # speed of light in m/s
G = 6.674e-11            # gravitational constant (m^3 kg^-1 s^-2)
PARSEC_KM = 3.086e13     # km per parsec
PARSEC_M = 3.086e16      # m per parsec

# --- Gravitational dilation model -------------------------------------------
# Both Earth and the server sit in the same field of catalog stars. We use the
# weak-field metric: a clock at gravitational potential Phi ticks at rate
# sqrt(1 + 2*Phi/c^2) relative to flat spacetime (Phi < 0, so the factor < 1).
# Real interstellar potentials are ~1 part in 1e13 — invisible — so we apply a
# documented EXAGGERATION so that the dense solar neighborhood vs. deep voids
# produce a visible (few-to-tens-of-percent) spread. A softening length keeps
# the potential finite when a server is placed right on top of a star.
SOFTENING_M = 0.1 * PARSEC_M
GRAVITY_EXAGGERATION = 5.5e9
MAX_WELL_DEPTH = 0.7     # cap so the dilation factor stays real and sane


def galactic_to_cartesian(d: float, l: float, b: float) -> dict:
    l_rad = math.radians(l)
    b_rad = math.radians(b)
    return {
        "x": d * math.cos(b_rad) * math.cos(l_rad),
        "y": d * math.cos(b_rad) * math.sin(l_rad),
        "z": d * math.sin(b_rad),
    }


def light_latency(x: float, y: float, z: float) -> float:
    """Round-trip light-speed latency from Earth (0,0,0) to (x,y,z) in parsecs."""
    dist_pc = math.sqrt(x**2 + y**2 + z**2)
    dist_km = dist_pc * PARSEC_KM
    return (2 * dist_km) / C


def local_potential(x: float, y: float, z: float) -> float:
    """Newtonian gravitational potential magnitude at (x,y,z) in parsecs.

    Returns sum of G*M_i / r_eff over all catalog stars (J/kg, positive),
    with softening to avoid singularities. Larger = deeper in the field.
    """
    xs, ys, zs, masses_kg = load_star_arrays()
    dx = (x - xs) * PARSEC_M
    dy = (y - ys) * PARSEC_M
    dz = (z - zs) * PARSEC_M
    r = np.sqrt(dx * dx + dy * dy + dz * dz + SOFTENING_M ** 2)
    return float(np.sum(G * masses_kg / r))


def gravitational_dilation(potential: float) -> float:
    """Clock-rate factor (< 1) for a clock at the given potential magnitude.

    Returns dτ/dt relative to flat spacetime; 1.0 in a perfect void, smaller
    deeper in the gravitational field.
    """
    depth = min(GRAVITY_EXAGGERATION * 2 * potential / C_M_S ** 2, MAX_WELL_DEPTH)
    return math.sqrt(1 - depth)


@lru_cache(maxsize=1)
def earth_dilation_factor() -> float:
    """Earth's clock factor: it sits at the origin, deep in the dense solar
    neighborhood, so its clock runs slow relative to a distant void."""
    return gravitational_dilation(local_potential(0.0, 0.0, 0.0))


def server_dilation_factor(x: float, y: float, z: float) -> float:
    """The void server's clock factor, from the local potential at its position."""
    return gravitational_dilation(local_potential(x, y, z))


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
