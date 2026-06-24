# Void Ranger Glossary

Quick reference for the terms and metrics used in the dashboard. Each entry is the term in **bold** with a one-line summary, followed by the detail below it. Formulas are written in plain notation for quick reading; the fully typeset derivations live in the README's [Physics and Assumptions](../README.md#physics-and-assumptions) section.

**Cosmic Server** — the compute server you deploy in a cosmological void, where weak gravity makes its clock tick faster than Earth's.

The premise of the mode: escape Earth's gravitational well into near-empty space and your clock speeds up, so a fixed job finishes in less Earth time. Where you place it sets **both** levers at once — its *local gravity* (how fast its clock runs) and its *distance* (how long the round-trip signal takes). Click the map to place it, or enter galactic coordinates in the panel.

**Orbit marker (orbit-ring)** — the cyan ring and drifting sparkles drawn around the deployed Cosmic Server.

A purely **visual locator** that makes the server easy to spot in the dense star field — think of it as a "you placed it here" highlight on the cyan sphere at its center. It does **not** represent a physical orbit or any physics: the server isn't orbiting a star or planet, and the ring's size and rotation carry no meaning. It exists only so the server doesn't get lost among the 8,920 catalog stars.

**Star labels** — the names drawn on the map for the brightest stars in view, plus the hover tooltip for any star.

To stay readable, only the **up to 8 brightest stars with proper names** inside the current view are labeled at once (the set re-evaluates as you orbit/zoom). **Hovering** any star — even the ~96% with no proper name — shows a tooltip with its name or catalog designation (Bayer/Flamsteed, else HD/HIP), constellation, distance in parsecs, and apparent magnitude. Names and magnitudes come from the HYG catalog; labels are purely informational and carry no physics.

**Task Workload Size** — how much compute the job needs, expressed as a duration in hours.

A proxy for job size measured in time rather than FLOPs or rows: "this job needs *N* hours of CPU time." The model assumes the same job costs the same amount of compute time on either machine (identical hardware), each measured in that machine's *own* clock — what differs is how fast those clocks tick. The field accepts hours; internally the physics works in seconds (`seconds = hours × 3600`).

**Distance from Earth** — straight-line Earth↔server separation, shown in parsecs (with light-years and miles).

Computed as `d = √(x² + y² + z²)`. It's the single input to communication latency (`2d/c`); it does **not** affect the clock rate. `1 pc ≈ 3.26 ly ≈ 1.92×10¹³ mi`.

**Server Clock Advantage** — how fast the Cosmic Server's clock ticks relative to Earth's; `>1` (cyan) is a void advantage, `<1` (red) means it sits in a denser region than Earth.

Computed as `advantage = f_server / f_earth`, where `f = √(1 + 2Φ/c²)` is a location's clock rate and `Φ` is the gravitational potential there (the softened sum of `−G·Mᵢ/r` over all catalog stars). Earth sits in the dense solar neighborhood, so `f_earth < 1` (slow clock); a deep void has `Φ → 0`, so `f_server → 1` (fast). `1.063×` means the server ticks 6.3% faster than Earth, so it finishes a job in less Earth time: `earth_compute = task ÷ advantage`. Real interstellar dilation is ~1 part in 10¹³ (invisible), so a `GRAVITY_EXAGGERATION` constant scales it into a visible few-percent effect — relative comparisons between placements are faithful; the absolute magnitude is not. For the full model (how proximity to other stars affects this, softening, and a worked example), see the [Gravitational Field Model](gravitational-field.md).

**Earth Compute Time** — how much Earth time passes while the server completes the task.

`earth_compute = task_seconds × (f_earth / f_server) = task ÷ advantage`. When the server's clock runs faster (advantage `> 1`), Earth ages less than the job's own runtime, so the work effectively finishes sooner than running it locally would. (Deep dive: [Efficiency & Breakeven](efficiency-model.md).)

**Communication Cost** — the round-trip light-speed delay to the server and back.

`comm_cost = 2d / c`. It's fixed by distance and independent of job size — you pay the same round trip whether the job is tiny or enormous. This is the tax the dilation savings must overcome. (Deep dive: [Light-Speed Latency](light-latency.md).)

**Earth Wait Time** — the total time an Earth observer waits, end to end.

`earth_wait = earth_compute + comm_cost`: dispatch the job, wait for the server to compute it, and wait for the result to travel back. It differs from Earth Compute Time by exactly the Communication Cost. (Deep dive: [Efficiency & Breakeven](efficiency-model.md).)

**Net Gain / Net Loss** — whether offloading beats just running the job on Earth.

`net_gain = task_seconds − earth_wait`. Positive (green) means the Cosmic Server saves time overall; negative (red) means the round-trip latency outweighs the dilation benefit. The ▲/▼ arrow points up for a net gain, down for a net loss. (Deep dive: [Efficiency & Breakeven](efficiency-model.md).)

**Breakeven Workload** — the smallest task size that pays off at the clicked location.

`breakeven = comm_cost / (1 − f_earth/f_server)`. It depends only on the placement, not the current task size. Below it, the fixed latency dominates (net loss); above it, the dilation savings win. It reads **green** once your Task Workload Size clears it, **red** otherwise, and **"none"** where the spot has no time advantage (`advantage ≤ 1`), since no job size could ever win there. (Deep dive: [Efficiency & Breakeven](efficiency-model.md).)

**Find deepest void / Best spot for this task** — the two auto-placement buttons (with an adjustable search radius).

*Find deepest void* searches the volume within the radius for the **lowest local gravitational potential** — the emptiest pocket, farthest from *all* stars (not the point farthest from Earth), where the clock runs fastest. *Best spot for this task* instead maximizes **net gain** (`task·(1 − f_earth/f_server) − latency`), balancing the void's clock advantage against light-delay latency for the current Task Workload Size. The radius is a latency budget, not a gravity setting. Full write-up: [Void Finding](void-finding.md).

## Cosmic Web scale

**Scale toggle** — the top-bar switch between **Solar Neighborhood** (stars, parsecs), **Cosmic Web** (2MRS galaxies, megaparsecs), and **Deep Field** (GLADE+ galaxies, megaparsecs).

All three run the *same* model — place a node in a void, weigh the clock advantage against light-delay latency. Switching swaps the catalog, the distance unit (pc ↔ Mpc), and the gravity sources (stars ↔ galaxies). The Deep Field additionally streams binary LOD tiles instead of one JSON and reads a precomputed potential grid. Full write-ups: [The Cosmic Web scale](cosmic-web.md) · [The Deep Field scale](deep-field.md).

**Galaxy (Cosmic Web)** — a point in the galaxy field, from the 2MASS Redshift Survey (2MRS).

~43,500 galaxies positioned by Hubble distance (`d = cz / H0`, `H0 = 70`); ~120 Mpc median, reaching a few hundred Mpc. Mass is a crude K-band stellar-mass proxy. 18 famous galaxies (Andromeda, Centaurus A, …) are anchored at literature distances and labeled by name; hovering any other shows its 2MASX designation, distance, and magnitude.

**Megaparsec (Mpc)** — the Cosmic Web distance unit; 1 Mpc ≈ 3.26 million light-years ≈ 10⁶ pc.

At these distances round-trip latency `2d/c` is enormous (~327 million years at 50 Mpc, ~1.3 billion at 200 Mpc), so only huge jobs in *nearby* voids ever net a gain — the trade-off the dashboard exists to show.

**Cosmic void** — a genuinely under-dense region of the cosmic web (few galaxies, weak gravity), where a node's clock runs fastest.

Unlike the loose "gap between nearby stars" at solar scale, these are *real* voids in large-scale structure. *Find deepest void* at this scale points at one. The gravitational-redshift difference between voids and galaxy clusters is a real, measured effect — so the cosmic scale uses a much smaller exaggeration than the stellar scale.

## Deep Field scale

**GLADE+** — the ~22.5-million-galaxy catalog behind the Deep Field scale (VizieR `VII/291`).

Only rows with a usable luminosity distance (`d_L ≤ 500 Mpc`) are kept, so the rendered 3-D set is smaller than the full 23.2 M rows. Galaxies are ranked by apparent brightness (W1, else B, else K) so coarse tiles show the prominent ones first. Full write-up: [The Deep Field scale](deep-field.md).

**LOD tile** — a "level of detail" chunk of the galaxy field: a headerless little-endian Float32 `.bin` of interleaved `x,y,z` in Mpc (12 bytes/galaxy).

The frontend streams these instead of one big JSON: coarse tiles load first, finer tiles refine on zoom. Points within a tile are brightness-ordered, so any prefix is a valid downsample. Point count = `byteLength / 12`.

**Octree / octant** — the spatial tree the tiles are organized into: each node's cube is recursively split into 8 **octants** (children), so the streamer can load only the regions in view at the needed detail.

Node ids encode the path: root `"0"`, a child appends its octant digit `0..7`. The tree is *sparse* — only non-empty octants are listed in the manifest.

**Voxel grid (potential grid)** — a precomputed 3-D array of the gravitational potential (J/kg) on a regular cube of cells (**voxels**), shape `(nz, ny, nx)`.

It lets the backend read the local potential anywhere in the ±500 Mpc cube without re-summing 22.5 M galaxies, so the Deep Field's *Find deepest void* / *Best spot* are **O(voxels)** — independent of catalog size. The grid stores the *raw* potential; the teaching exaggeration is applied once in the dilation model.

**Trilinear interpolation** — how a value at an arbitrary point is read from the voxel grid: a weighted blend of the 8 surrounding voxel centers along x, y, and z.

It makes the gridded potential continuous everywhere in the cube (points past the outermost voxel centers clamp to the nearest edge — no extrapolation, no NaN).
