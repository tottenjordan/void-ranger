# Void Ranger — Documentation

Reference docs for [Void Ranger](../README.md). Start with the project
[README](../README.md) for setup and an overview; the files here go deeper on the
model and the on-screen terms.

## Contents

| Doc | What's in it |
|-----|--------------|
| [Glossary](GLOSSARY.md) | One-line definitions of every on-screen metric and term (both modes), with the quick formula for each. |
| [Gravitational Field Model](gravitational-field.md) | How the gravitational potential — and thus the clock rate — is computed at any coordinate: the softened sum over all catalog stars, the softening length, proximity-to-a-star behavior, masses, and a worked example. |
| [Efficiency & Breakeven](efficiency-model.md) | The offload-vs-local math: Earth Compute Time, Earth Wait Time, Net Gain/Loss, and the Breakeven workload derivation, with a worked example. |
| [Light-Speed Latency](light-latency.md) | The round-trip communication delay (`2d/c`), why it limits void-hunting, and a distance→delay table. |

## How they fit together

The three deep dives mirror the data flow of a single server placement:

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
```

All the math lives in [`backend/app/services/physics.py`](../backend/app/services/physics.py);
each deep dive ends with a "code map" pointing at the exact functions.

## Images

[`images/`](images/) holds the README banner GIFs and dashboard screenshots.
