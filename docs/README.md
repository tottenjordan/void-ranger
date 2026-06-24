# Void Ranger — Documentation

Reference docs for [Void Ranger](../README.md). Start with the project
[README](../README.md) for setup and an overview; the files here go deeper on the
model and the on-screen terms.

## Contents

| Doc | What's in it |
|-----|--------------|
| [Glossary](GLOSSARY.md) | One-line definitions of every on-screen metric and term, with the quick formula for each. |
| [Gravitational Field Model](gravitational-field.md) | How the gravitational potential — and thus the clock rate — is computed at any coordinate: the softened sum over all catalog stars, the softening length, proximity-to-a-star behavior, masses, and a worked example. |
| [Efficiency & Breakeven](efficiency-model.md) | The offload-vs-local math: Earth Compute Time, Earth Wait Time, Net Gain/Loss, and the Breakeven workload derivation, with a worked example. |
| [Light-Speed Latency](light-latency.md) | The round-trip communication delay (`2d/c`), why it limits void-hunting, and a distance→delay table. |
| [Void Finding](void-finding.md) | How the app auto-locates good placements: what "low gravity" really means (sum over all stars, not distance from Earth), the search methods, and what the **Find deepest void** / **Best spot** buttons do. |
| [Scaling the Universe](scaling-the-universe.md) | Options for growing beyond the solar neighborhood — bigger star/galaxy catalogs (HYG, Gaia, GLADE+), the data/rendering/physics trade-offs, GCP fit, and the chosen cosmic-web direction. |
| [Cosmic Web scale](cosmic-web.md) | The galaxy-scale mode (2MRS, megaparsecs): catalog, the scale-parameterized physics, real cosmic voids, latency in millions of years, and caveats. |
| [Deep Field scale](deep-field.md) | The big-data galaxy mode (GLADE+, ~22.5 M, megaparsecs): the binary LOD tile + potential-grid formats, the O(voxels) void search, the ±500 Mpc bound, calibration, the GCP-ready/local-first pipeline, and how the frontend streams it. |

## How they fit together

The deep dives mirror the data flow of a single server placement:

```
where you place the server (x, y, z)
        │
        ├─ local gravity  ─────────────►  Gravitational Field Model
        │     (f_earth, f_server, clock advantage)
        │
        ├─ distance from Earth  ───────►  Light-Speed Latency
        │     (round-trip 2d/c)
        │
        └─ both feed ──────────────────►  Efficiency & Breakeven
              (Earth compute/wait time, net gain, breakeven)

  …and Void Finding inverts this: it searches placements to optimize
  the gravity (deepest void) or the net gain (best spot for a task).
```

All the math lives in [`backend/app/services/physics.py`](../backend/app/services/physics.py);
each deep dive ends with a "code map" pointing at the exact functions.

## Plans

Numbered implementation plans (goals, tasks, status) live in
[`plans/`](plans/) — see the [plans index](plans/README.md).

## Images

[`images/`](images/) holds the README banner GIFs and dashboard screenshots.
