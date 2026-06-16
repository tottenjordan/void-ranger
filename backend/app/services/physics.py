import math

C = 299_792.458
G = 6.674e-11
SOLAR_MASS = 1.989e30
PARSEC_KM = 3.086e13


def galactic_to_cartesian(d: float, l: float, b: float) -> dict:
    l_rad = math.radians(l)
    b_rad = math.radians(b)
    return {
        "x": d * math.cos(b_rad) * math.cos(l_rad),
        "y": d * math.cos(b_rad) * math.sin(l_rad),
        "z": d * math.sin(b_rad),
    }


def light_latency(x: float, y: float, z: float) -> float:
    dist_pc = math.sqrt(x**2 + y**2 + z**2)
    dist_km = dist_pc * PARSEC_KM
    return (2 * dist_km) / C


def time_dilation_factor(mass_kg: float, radius_m: float) -> float:
    rs = (2 * G * mass_kg) / (C * 1000) ** 2
    return math.sqrt(1 - rs / radius_m)


def lorentz_factor(v: float) -> float:
    return 1 / math.sqrt(1 - (v / C) ** 2)


def compute_efficiency(task_seconds: float, dilation_factor: float,
                       latency_seconds: float) -> dict:
    local_time = task_seconds * dilation_factor
    earth_wait_time = local_time + latency_seconds
    net_gain = task_seconds - earth_wait_time
    return {
        "local_time": local_time,
        "earth_wait_time": earth_wait_time,
        "net_gain": net_gain,
    }
