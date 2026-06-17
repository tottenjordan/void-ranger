# ChronoCloud Glossary

Quick reference for the terms and metrics used in the two dashboards. Each entry is the term in **bold** with a one-line summary, followed by the detail below it. Formulas are written in plain notation for quick reading; the fully typeset derivations live in the README's [Physics and Assumptions](../README.md#physics-and-assumptions) section.

## Deep-Space Cloud Compute

**Cosmic Server** — the compute server you deploy in a cosmological void, where weak gravity makes its clock tick faster than Earth's.

The premise of the mode: escape Earth's gravitational well into near-empty space and your clock speeds up, so a fixed job finishes in less Earth time. Where you place it sets **both** levers at once — its *local gravity* (how fast its clock runs) and its *distance* (how long the round-trip signal takes). Click the map to place it, or enter galactic coordinates in the panel.

**Orbit marker (orbit-ring)** — the cyan ring and drifting sparkles drawn around the deployed Cosmic Server.

A purely **visual locator** that makes the server easy to spot in the dense star field — think of it as a "you placed it here" highlight on the cyan sphere at its center. It does **not** represent a physical orbit or any physics: the server isn't orbiting a star or planet, and the ring's size and rotation carry no meaning. It exists only so the server doesn't get lost among the 8,920 catalog stars.

**Task Workload Size** — how much compute the job needs, expressed as a duration in hours.

A proxy for job size measured in time rather than FLOPs or rows: "this job needs *N* hours of CPU time." The model assumes the same job costs the same amount of compute time on either machine (identical hardware), each measured in that machine's *own* clock — what differs is how fast those clocks tick. The field accepts hours; internally the physics works in seconds (`seconds = hours × 3600`). Only used in Deep-Space mode.

**Distance from Earth** — straight-line Earth↔server separation, shown in parsecs (with light-years and miles).

Computed as `d = √(x² + y² + z²)`. It's the single input to communication latency (`2d/c`); it does **not** affect the clock rate. `1 pc ≈ 3.26 ly ≈ 1.92×10¹³ mi`.

**Server Clock Advantage** — how fast the Cosmic Server's clock ticks relative to Earth's; `>1` (green) is a void advantage, `<1` (red) means it sits in a denser region than Earth.

Computed as `advantage = f_server / f_earth`, where `f = √(1 + 2Φ/c²)` is a location's clock rate and `Φ` is the gravitational potential there (the softened sum of `−G·Mᵢ/r` over all catalog stars). Earth sits in the dense solar neighborhood, so `f_earth < 1` (slow clock); a deep void has `Φ → 0`, so `f_server → 1` (fast). `1.063×` means the server ticks 6.3% faster than Earth, so it finishes a job in less Earth time: `earth_compute = task ÷ advantage`. Real interstellar dilation is ~1 part in 10¹³ (invisible), so a `GRAVITY_EXAGGERATION` constant scales it into a visible few-percent effect — relative comparisons between placements are faithful; the absolute magnitude is not.

**Earth Compute Time** — how much Earth time passes while the server completes the task.

`earth_compute = task_seconds × (f_earth / f_server) = task ÷ advantage`. When the server's clock runs faster (advantage `> 1`), Earth ages less than the job's own runtime, so the work effectively finishes sooner than running it locally would.

**Communication Cost** — the round-trip light-speed delay to the server and back.

`comm_cost = 2d / c`. It's fixed by distance and independent of job size — you pay the same round trip whether the job is tiny or enormous. This is the tax the dilation savings must overcome.

**Earth Wait Time** — the total time an Earth observer waits, end to end.

`earth_wait = earth_compute + comm_cost`: dispatch the job, wait for the server to compute it, and wait for the result to travel back. It differs from Earth Compute Time by exactly the Communication Cost.

**Net Gain / Net Loss** — whether offloading beats just running the job on Earth.

`net_gain = task_seconds − earth_wait`. Positive (green) means the Cosmic Server saves time overall; negative (red) means the round-trip latency outweighs the dilation benefit. The ▲/▼ arrow shows whether the value rose or fell since your last change.

**Breakeven Workload** — the smallest task size that pays off at the clicked location.

`breakeven = comm_cost / (1 − f_earth/f_server)`. It depends only on the placement, not the current task size. Below it, the fixed latency dominates (net loss); above it, the dilation savings win. It reads **green** once your Task Workload Size clears it, **red** otherwise, and **"none"** where the spot has no time advantage (`advantage ≤ 1`), since no job size could ever win there.

## Interplanetary DevOps 🚧 WIP

> 🚧 **Work in progress** — this mode is parked while Deep-Space Cloud Compute is the focus. See the [Roadmap](../README.md#roadmap).

**Light Delay (Earth–Mars)** — the one-way time for a signal to cross between the planets, ~750 s (12.5 min) at a mid-range distance.

`t_delay = d / c`, with `d ≈ 2.25×10⁸ km` (the true range is 55–401 million km). Because nothing travels faster than light, Earth always *sees* a Mars event this long after it actually happened — the source of all the ordering trouble.

**Relativistic Sync Protocol** — the 0–100% slider that compensates for the light delay to restore correct event ordering.

It subtracts a fraction of the *known* light delay from incoming Mars timestamps: a Mars event at time `t` is placed at `t + t_delay × (1 − syncOffset)`. At 100% the residual delay is zero and the ledger orders correctly; at 0% events land late and scramble. It's loosely named — it models signal-propagation delay and event-ordering correction (Lamport-clock territory), not real relativistic time dilation.

**Drift / Causality Conflict** — an out-of-order transaction caused by the light delay.

When a Mars transaction that truly happened first is *observed* on Earth after a later Earth transaction, merging the two ledgers by arrival time scrambles the real order — breaking last-write-wins and similar consistency assumptions. The ring gauge reports the drift rate (e.g. 1 conflict in 50 transactions = 2%); raising the sync slider clears it.
