"""Emit real-physics plot data for the educational figures.

Imports the REAL backend physics (app.services.physics) — no math is
reimplemented here — and writes one JSON file per plot into
``backend/scripts/figures/_data/`` (git-ignored).

Run (idempotent):

    cd backend && PYTHONPATH=. uv run python scripts/figures/gen_plot_data.py

Each JSON follows a single schema so a downstream plot step can read them
uniformly::

    {
      "title":   str,
      "x_label": str,
      "y_label": str,
      "x":       [float, ...],
      "series":  [{"name": str, "y": [float, ...]}, ...],
      "annotations": [ ... ]            # optional, plot-specific
    }

For the bar chart (clock_advantage_per_scale) the x axis is categorical
(scale names) and each series carries one y value per category.
"""

import json
import math
from pathlib import Path

from app.services.physics import (
    SCALES,
    breakeven_task_seconds,
    compute_efficiency,
    earth_dilation_factor,
    find_deepest_void,
    light_latency,
    server_dilation_factor,
)

# --- output location --------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent / "_data"

# --- time-unit helpers ------------------------------------------------------
DAY_S = 86_400.0
YEAR_S = 365.25 * DAY_S

SCALE_ORDER = ["solar", "cosmic", "deepfield"]

# Search radius per scale (the latency budget, in the scale's length unit).
# Matches find_deepest_void's default of 300 for every scale.
MAX_DISTANCE = {"solar": 300.0, "cosmic": 300.0, "deepfield": 300.0}

# Task sizes used for the net-gain curve, labeled as series.
#
# The solar latency exaggeration is large: round-trip light delay reaches
# ~3.3 yr per parsec, while the void's clock advantage saves only a few percent
# of task time. So the break-even task size along the solar void axis sits
# around ~24k-68k YEARS (verified via breakeven_task_seconds). Sub-year tasks
# are therefore latency-dominated at EVERY distance and never cross zero. To
# reveal the educational crossover we bracket that break-even band with three
# multi-millennium task sizes: the smallest stays negative (latency wins), the
# largest stays positive (dilation wins), and the middle one crosses zero.
NETGAIN_TASKS = [
    ("10,000 yr task", 10_000 * YEAR_S),
    ("30,000 yr task", 30_000 * YEAR_S),
    ("100,000 yr task", 100_000 * YEAR_S),
]

N_SAMPLES = 60  # distance samples per swept curve


def _unit_vector(point: dict) -> tuple[float, float, float]:
    """Unit vector pointing toward a deepest-void coordinate dict."""
    x, y, z = point["x"], point["y"], point["z"]
    norm = math.sqrt(x * x + y * y + z * z)
    if norm == 0:
        return (0.0, 0.0, 0.0)
    return (x / norm, y / norm, z / norm)


def _distance_samples(max_d: float, n: int = N_SAMPLES) -> list[float]:
    """n distances from near 0 out to max_d (skip exactly 0 to avoid a
    degenerate origin sample that coincides with Earth)."""
    step = max_d / n
    return [round(step * (i + 1), 6) for i in range(n)]


def _void_axis(scale: str) -> tuple[tuple[float, float, float], float, list[float]]:
    """Return (unit_vector_toward_void, void_distance, distance_samples) for a
    scale, sweeping out to the deepest-void distance (capped at the search
    radius)."""
    max_d = MAX_DISTANCE[scale]
    void = find_deepest_void(max_distance_pc=max_d, scale=scale)
    ux, uy, uz = _unit_vector(void)
    void_dist = math.sqrt(void["x"] ** 2 + void["y"] ** 2 + void["z"] ** 2)
    sweep_to = void_dist if void_dist > 0 else max_d
    return (ux, uy, uz), void_dist, _distance_samples(sweep_to)


def _write(name: str, payload: dict, samples: list[tuple[str, object]]) -> None:
    """Write payload to _data/<name> and print a short sanity summary."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / name
    path.write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {path}")
    for label, value in samples:
        print(f"    {label}: {value}")


# --- plot 1: net gain vs distance (solar) -----------------------------------
def gen_netgain_vs_distance() -> None:
    scale = "solar"
    (ux, uy, uz), void_dist, dists = _void_axis(scale)
    f_earth = earth_dilation_factor(scale)

    series = []
    for name, task_s in NETGAIN_TASKS:
        ys = []
        for d in dists:
            x, y, z = ux * d, uy * d, uz * d
            f_server = server_dilation_factor(x, y, z, scale)
            latency = light_latency(x, y, z, scale)
            eff = compute_efficiency(task_s, f_earth, f_server, latency)
            ys.append(eff["net_gain"] / YEAR_S)  # net gain in YEARS
        series.append({"name": name, "y": ys})

    payload = {
        "title": "Net gain vs distance (solar scale, toward deepest void)",
        "x_label": "Distance from Earth (parsecs)",
        "y_label": "Net gain (years)",
        "x": dists,
        "series": series,
        "annotations": [
            {"type": "hline", "y": 0.0, "label": "break-even (net gain = 0)"},
        ],
    }
    samples = [
        ("void distance (pc)", round(void_dist, 2)),
        ("f_earth", round(f_earth, 6)),
    ]
    for s in series:
        samples.append((f"{s['name']} net gain @max-d (yr)", round(s["y"][-1], 4)))
    _write("netgain_vs_distance.json", payload, samples)


# --- plot 2: breakeven task size vs distance (per scale) ---------------------
def gen_breakeven_vs_distance() -> None:
    series = []
    summary = []
    # Common x axis: fractional distance (0..1) along each scale's void axis,
    # so the three scales (different length units) share one normalized axis.
    fracs = [round((i + 1) / N_SAMPLES, 6) for i in range(N_SAMPLES)]

    for scale in SCALE_ORDER:
        (ux, uy, uz), void_dist, _ = _void_axis(scale)
        f_earth = earth_dilation_factor(scale)
        sweep_to = void_dist if void_dist > 0 else MAX_DISTANCE[scale]
        ys = []
        for frac in fracs:
            d = sweep_to * frac
            x, y, z = ux * d, uy * d, uz * d
            f_server = server_dilation_factor(x, y, z, scale)
            latency = light_latency(x, y, z, scale)
            be = breakeven_task_seconds(f_earth, f_server, latency)
            # None => server not in a weaker field (no winning task size).
            # NaN is JSON-encoded as null below for plotability.
            ys.append(be / DAY_S if be is not None else None)
        series.append({"name": scale, "y": ys})
        # last finite value for the summary
        last_finite = next((v for v in reversed(ys) if v is not None), None)
        summary.append(
            (f"{scale} breakeven @void (days)",
             round(last_finite, 4) if last_finite is not None else None)
        )

    payload = {
        "title": "Break-even task size vs distance (per scale)",
        "x_label": "Fractional distance toward deepest void (0 = Earth, 1 = void)",
        "y_label": "Break-even task size (days, log scale)",
        "y_scale": "log",
        "x": fracs,
        "series": series,
    }
    _write("breakeven_vs_distance.json", payload, summary)


# --- plot 3: round-trip light delay vs distance (per scale) ------------------
def gen_latency_vs_distance() -> None:
    # light_latency returns ROUND-TRIP (2d/c) per its docstring. All three
    # series share a single unit (YEARS) so the chart is honest; the scales
    # span ~10^1 to ~10^9 years, so a log y-scale is required for them to
    # coexist on one axis.
    series = []
    summary = []
    fracs = [round((i + 1) / N_SAMPLES, 6) for i in range(N_SAMPLES)]

    for scale in SCALE_ORDER:
        (ux, uy, uz), void_dist, _ = _void_axis(scale)
        sweep_to = void_dist if void_dist > 0 else MAX_DISTANCE[scale]
        ys = []
        for frac in fracs:
            d = sweep_to * frac
            x, y, z = ux * d, uy * d, uz * d
            ys.append(light_latency(x, y, z, scale) / YEAR_S)
        series.append({"name": scale, "y": ys})
        summary.append((f"{scale} round-trip delay min-max (yr)",
                        (round(min(ys), 4), round(max(ys), 4))))

    payload = {
        "title": "Round-trip light delay vs distance (per scale)",
        "x_label": "Fractional distance toward deepest void (0 = Earth, 1 = void)",
        "y_label": "Round-trip light delay (years, log scale)",
        "y_scale": "log",
        "note": "light_latency is round-trip (2d/c), converted to years; all "
                "scales share one log axis spanning ~10^1 to ~10^9 years.",
        "x": fracs,
        "series": series,
    }
    _write("latency_vs_distance.json", payload, summary)


# --- plot 4: deepest-void clock advantage per scale (bar) -------------------
def gen_clock_advantage_per_scale() -> None:
    advantages = []
    summary = []
    for scale in SCALE_ORDER:
        max_d = MAX_DISTANCE[scale]
        void = find_deepest_void(max_distance_pc=max_d, scale=scale)
        f_earth = earth_dilation_factor(scale)
        f_server = server_dilation_factor(void["x"], void["y"], void["z"], scale)
        # void-favoring ratio: server in the void runs FASTER than Earth (>1).
        adv = f_server / f_earth
        advantages.append(adv)
        summary.append((f"{scale} clock advantage", round(adv, 4)))

    payload = {
        "title": "Deepest-void clock advantage by scale",
        "x_label": "Scale",
        "y_label": "Clock advantage (f_server / f_earth)",
        "x": SCALE_ORDER,
        "series": [{"name": "clock advantage", "y": advantages}],
        "annotations": [
            {"type": "band", "y_min": 1.05, "y_max": 1.10,
             "label": "documented teaching band (~1.05-1.10)"},
            {"type": "hline", "y": 1.0, "label": "Earth (no advantage)"},
        ],
    }
    _write("clock_advantage_per_scale.json", payload, summary)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"writing plot data into {DATA_DIR}")
    gen_netgain_vs_distance()
    gen_breakeven_vs_distance()
    gen_latency_vs_distance()
    gen_clock_advantage_per_scale()
    print("\ndone.")


if __name__ == "__main__":
    main()
