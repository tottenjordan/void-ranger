# ChronoCloud

An interactive educational web application demonstrating the effects of relativistic computing and time dilation.

## Simulation Modes

- **Interplanetary DevOps** — Synchronize database ledgers between Earth and Mars, dealing with light-speed delay and micro-time drifts. Adjust a relativistic sync protocol slider to correct transaction ordering in real time.
- **Deep-Space Cloud Compute** — Place computational servers in cosmological voids where clocks tick faster than Earth's (weaker gravitational field), then balance the dilation benefit against light-speed communication latency.

## Architecture

```
React Frontend (Vite + Tailwind + Three.js + Chart.js)
  │
  ├── /api/*  →  FastAPI Backend (Python)
  │                ├── POST /api/physics/cartesian    — galactic → Cartesian coords
  │                ├── POST /api/physics/efficiency   — time dilation + latency metrics
  │                └── GET  /api/stars                — processed HYG star catalog
  │
  └── Star data  ←  HYG Database (8,920 stars, processed from v41)
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+

## Setup

### Backend

```bash
cd backend
uv sync --all-extras
source .venv/bin/activate
```

### Process Star Data (one-time)

The processed `stars.json` is included in the repo. To regenerate from the raw HYG CSV:

```bash
# Download HYG v41 CSV (~32MB)
curl -L -o data/hygdata_v41.csv \
  "https://raw.githubusercontent.com/astronexus/HYG-Database/main/hyg/CURRENT/hygdata_v41.csv"

# Process into stars.json (8,920 stars at magnitude ≤ 6.5)
python scripts/process_stars.py
```

The actively maintained HYG source is at https://codeberg.org/astronexus/hyg.

### Frontend

```bash
cd frontend
npm install
```

## Development

Start the backend and frontend in separate terminals:

```bash
# Terminal 1 — Backend
cd backend
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open http://localhost:5173

## Simulation Modes — In Depth

### Deep-Space Cloud Compute (Far-Future Mode)

**Concept:** In a far-future scenario, humanity places computational servers in cosmological voids — vast regions of space with negligible gravitational influence. Clocks tick slower in stronger gravitational fields (general relativity), and Earth sits in the gravitational wells of the Sun and Milky Way. A server in a void experiences weaker gravity, so its clock ticks *faster* than Earth's — it can complete days of computation while only hours pass on Earth. The tradeoff: the results must travel back at light speed, and the farther the void, the longer the round-trip delay.

**Features:**
- **3D Galaxy Map** — An interactive star field rendered from the HYG astronomical catalog (8,920 real stars). Rotate, zoom, and pan to explore. Background stars twinkle; data stars are color-coded by luminosity (brighter stars appear warmer).
- **Server Placement** — Click anywhere on the map or enter galactic coordinates (distance, longitude, latitude) to deploy a void server. The server appears as a floating, glowing sphere surrounded by gravitational field rings and sparkles.
- **Light-Speed Communication Line** — A dashed line connects Earth (green marker at origin) to your server, with an animated signal pulse traveling back and forth. The label shows distance in parsecs and round-trip travel time.
- **Metrics Dashboard** — Three cards update in real time with animated value transitions:
  - *Earth Compute Time* — how much Earth time passes while the void server completes the task (less than the raw task duration, because the server's clock is faster)
  - *Earth Wait Time* — compute time + round-trip light delay
  - *Net Gain/Loss* — whether the dilation benefit outweighs the communication cost
- **Task Duration Control** — Adjust the "Task (s)" input in the header to simulate different workload sizes. Longer tasks benefit more from time dilation.
- **Note on Scale** — The gravitational dilation effect is pedagogically exaggerated. Real Sun-Earth time dilation is ~1 part per billion. The dashboard models Earth in an extreme gravitational well (near a neutron-star-mass object) to make the effect visible and the tradeoffs explorable.
- **Camera Fly-To** — The camera automatically frames both Earth and the server when you place one.

**What problems does it address?**
- Builds intuition for the competing forces in relativistic computing: placing a server in a gravitational void speeds up its clock relative to Earth's, but light-speed latency adds communication overhead.
- Demonstrates that "farther into the void" is not always better — at some distance, the latency cost exceeds the dilation benefit.
- Provides a hands-on way to explore the Schwarzschild metric without equations.
- Illustrates a key asymmetry: Earth's gravitational well slows our clocks, and escaping it (into a void) is computationally advantageous — the opposite of the sci-fi trope of "computing near a black hole."

**Try this:** Place a server at 1 parsec, note the Net Gain/Loss, then move it to 100 parsecs. Watch how the latency dominates at large distances even though the server's clock advantage is constant. Now increase the task duration to 1,000,000 seconds — at what distance does the dilation benefit finally overcome the latency cost?

#### Understanding the Task Workload Size

The **Task (s)** input in the header is the *size of the computational job*, expressed as a duration: how many seconds of compute the job requires on whatever machine runs it. (It only affects this Deep-Space mode; the Interplanetary ledger mode ignores it.)

**What it represents:** Think of it as "this job needs *N* seconds of CPU time to finish." A small value like `3600` (1 hour) is a quick job; a large value like `1e12` (≈31,700 years) is a massive batch computation. It is a proxy for workload size measured in time rather than FLOPs or rows. The model assumes the **same job costs the same number of compute-seconds on either machine** (identical hardware), each measured in that machine's *own* clock — what differs is how fast those clocks tick relative to Earth.

**Why it's the key lever:** Task size determines whether offloading to a void server actually pays off. From the efficiency formula:

$$
\text{net gain} = \underbrace{t_\text{task} \cdot (1 - f_\text{earth})}_{\text{dilation benefit (scales with size)}} - \underbrace{t_\text{latency}}_{\text{fixed cost}}
$$

- The **dilation benefit** grows linearly with task size. A faster-ticking void server saves a *percentage* of the runtime (~5% with the default well), so the bigger the job, the more absolute time saved.
- The **latency cost** is fixed — it depends only on distance, not job size. You pay the same round-trip light delay whether the job is tiny or enormous.

So there is a **break-even task size**: below it, the fixed communication overhead dominates and offloading is a net loss; above it, the dilation savings overtake the latency and you come out ahead. This is why the walkthrough screenshot needs a $10^{12}$ s task to show a positive net gain at 20 pc — a 1-hour job at that distance would be a massive net loss.

**Real-world analogy:** It is the same calculus as deciding whether to ship a job to a distant data center. The network round-trip is a fixed tax, so it is only worth paying if the job is big enough that the remote machine's advantage (here, a faster clock; in reality, cheaper or faster hardware) outweighs the transit cost. Small jobs stay local; large jobs justify the trip.

---

### Interplanetary DevOps (Near-Future Mode)

**Concept:** In a near-future scenario, Earth and Mars each run database ledgers. Transactions originate on both planets, but Mars transactions take ~12.5 minutes (750 seconds) to reach Earth at light speed. Without compensation, Earth sees Mars transactions arriving late, causing ordering conflicts — a transaction that happened first on Mars might appear to happen after a later Earth transaction. The Relativistic Sync Protocol applies timestamp compensation to correct this.

**Features:**
- **Ledger Timeline Chart** — A Chart.js visualization showing Earth transactions (green) and Mars transactions (orange) plotted over time. Mars transactions are offset by the light-delay window. As you adjust the sync slider, the Mars line smoothly animates to its corrected position.
- **Light-Delay Zone** — A semi-transparent orange band on the chart represents the time window where Mars transactions are "in flight." The band shrinks as you increase sync compensation, directly visualizing the protocol's effect.
- **Conflict Markers** — Red dots and bands appear at exact timestamps where transaction ordering breaks down. These disappear as you increase compensation.
- **Data Drift Counter** — An SVG ring gauge showing accumulated ordering errors as both a count and percentage. Color transitions from green (no errors) through amber to red (high drift, with a glow effect).
- **Relativistic Sync Protocol Slider** — A gradient-tracked slider from 0% (no compensation) to 100% (full compensation) with tick marks and a dynamic description explaining the physics at each position.
- **Transaction Replay** — Press Play to watch transactions arrive in real time with a cyan playhead sweeping across the chart. The drift counter updates live as each transaction is processed. Speed controls (1x, 2x, 5x) let you watch at different rates. Pause, resume, or reset at any time.

**What problems does it address?**
- Demonstrates the real engineering challenge of distributed systems across light-speed delays — the same class of problem that GPS satellites solve today (GPS clocks are corrected for both gravitational and velocity-based time dilation).
- Shows why naive timestamp comparison fails in interplanetary networks and why protocols must account for propagation delay.
- Illustrates causality violations: a transaction that "happened first" can arrive second, breaking assumptions that underpin most database consistency models (e.g., last-write-wins).

**Try this:** Start with the slider at 0% and press Play. Watch the drift counter climb as Mars transactions arrive out of order. Pause, drag the slider to 100%, and replay — the conflicts disappear. Now try 50% — partial compensation reduces but doesn't eliminate drift. This is the core tradeoff real mission planners face.

## Example Walkthrough

### Deep-Space Cloud Compute

![Deep-Space Cloud Compute mode showing a void server deployed in the star field](docs/images/far-future.png)

This capture shows a void server deployed at **20 pc** with a **10¹² second** workload (set via the *Task (s)* field in the header). Reading the screen:

- The **green marker** at the center is Earth; the **cyan sphere** with an orbit ring and gravitational field rings is the deployed server. A dashed **communication line** connects them, with an animated signal pulse traveling the round trip.
- The **metrics row** shows the result: *Earth Compute Time* ≈ 30,108 yr (less than the 31,700 yr the task would take locally, because the server's clock runs faster), *Earth Wait Time* ≈ 30,238 yr (compute + round-trip light delay), and a **positive Net Gain of ~1,471 yr** (green) — offloading wins here.
- Try dragging the server farther out: the light-delay term grows until the Net Gain flips negative (red), demonstrating the latency/dilation tradeoff.

### Interplanetary DevOps

![Interplanetary DevOps mode showing Earth and Mars ledger timelines](docs/images/near-future.png)

This capture shows the ledger timeline with the **Relativistic Sync Protocol at 40%**. Reading the screen:

- **Green points** are Earth transactions; **orange points** are Mars transactions as seen from Earth, shifted right by the residual light delay. The faint **orange band** on the left is the light-delay window — it shrinks as you increase compensation.
- The **red dot** near the top marks a causality conflict (a transaction that arrived out of order). The **ring gauge** on the right reports the drift: 1 error across 50 transactions (2%).
- The slider description reads *"Partial compensation — ~375s residual delay."* Drag it to 100% and the conflict and drift clear; drag to 0% and they grow.
- Press **Play** to replay the transactions in real time with a sweeping playhead, at 1x/2x/5x speed.

## Physics & Assumptions

All physics lives in [`backend/app/services/physics.py`](backend/app/services/physics.py) as pure functions. This section documents each formula, its derivation, and the simplifying assumptions the simulation makes. The math is textbook-correct; some **parameters are deliberately exaggerated** for visibility, as noted below.

### Constants

| Symbol | Value | Meaning |
|--------|-------|---------|
| $c$ | $299{,}792.458\ \text{km/s}$ | Speed of light |
| $G$ | $6.674 \times 10^{-11}\ \text{m}^3\,\text{kg}^{-1}\,\text{s}^{-2}$ | Gravitational constant |
| $M_\odot$ | $1.989 \times 10^{30}\ \text{kg}$ | Solar mass |
| $1\ \text{pc}$ | $3.086 \times 10^{13}\ \text{km}$ | Parsec |

### 1. Galactic → Cartesian conversion

Converts a server's galactic coordinates — distance $d$ (parsecs), longitude $l$, latitude $b$ — into Cartesian coordinates for 3D rendering. This is the standard spherical-to-Cartesian transformation, where $b$ is the elevation above the galactic plane and $l$ is the azimuth:

$$
x = d \cos(b)\cos(l), \qquad
y = d \cos(b)\sin(l), \qquad
z = d \sin(b)
$$

### 2. Light-speed latency

Round-trip communication time from Earth at the origin to a server at $(x, y, z)$, in parsecs. The factor of 2 accounts for the round trip (dispatch the task, receive the result):

$$
t_\text{latency} = \frac{2 \, d}{c}, \qquad d = \sqrt{x^2 + y^2 + z^2}\ \ (\text{converted to km})
$$

*Verification:* a server 1 pc away yields a 6.52-year round trip, consistent with 1 pc ≈ 3.26 light-years one way.

### 3. Gravitational time dilation (Schwarzschild metric)

For a static clock at radius $r$ from a spherical mass $M$, the Schwarzschild metric gives the clock's tick rate relative to a clock at infinity (flat spacetime):

$$
\frac{d\tau}{dt} = \sqrt{1 - \frac{r_s}{r}}, \qquad r_s = \frac{2GM}{c^2}
$$

where $r_s$ is the **Schwarzschild radius**. In the void scenario, this factor describes **Earth's** clock — Earth sits deep in a gravitational well, so its clock runs *slow* (factor < 1). The void server sits in near-flat spacetime (factor ≈ 1), so it runs *faster* than Earth by $1 / \text{factor}$.

*Verification:* the code computes $r_s = 2954\ \text{m}$ for the Sun, matching the textbook value of ~2953 m.

### 4. Computation efficiency

Given a task requiring `task_seconds` of compute (in the local clock of whichever machine runs it), the model compares running it locally on Earth versus offloading to the void server:

$$
t_\text{compute} = t_\text{task} \cdot f_\text{earth}
$$

$$
t_\text{wait} = t_\text{compute} + t_\text{latency}
$$

$$
\text{net gain} = t_\text{task} - t_\text{wait}
$$

where $f_\text{earth}$ is Earth's dilation factor from §3, $t_\text{compute}$ is the Earth time elapsed during the offloaded computation, and $t_\text{wait}$ is the total Earth time from dispatch to receiving the result. The void server burns $t_\text{task}$ of its own (≈coordinate) time, during which Earth ages only $t_\text{task} \cdot f_\text{earth}$ — but you must wait $t_\text{latency}$ for the round trip. A **positive net gain** means offloading beats local execution.

### 5. Lorentz factor (special relativity)

Provided for velocity-based time dilation, where $v$ is in km/s:

$$
\gamma = \frac{1}{\sqrt{1 - (v/c)^2}}
$$

### 6. Interplanetary light delay (Near-Future mode)

Earth–Mars one-way signal delay is pure light-travel time (no relativity involved):

$$
t_\text{delay} = \frac{d_\text{Earth–Mars}}{c}
$$

With $d_\text{Earth–Mars} = 2.25 \times 10^8\ \text{km}$ (a realistic mid-range distance; the true range is 55–401 million km), this gives **750 s ≈ 12.5 min**. A Mars transaction at timestamp $t$ appears on Earth at $t + t_\text{delay}(1 - \text{syncOffset})$, where the sync slider applies compensation from 0 (none) to 1 (full).

### Assumptions & Caveats

These are intentional simplifications. They keep the simulation legible, but a physicist should know where it departs from reality:

1. **The gravitational dilation is fictional in scale.** The default places Earth at $r = 3 \times 10^4\ \text{m}$ (30 km) from a solar mass — *inside* the real Sun, so it only makes sense as a compact object (black hole / neutron star). This yields a ~5.3% effect. Real Sun–Earth dilation is ~1 part in $10^8$ — invisible on a dashboard. The exaggeration is deliberate and flagged in code.

2. **Net gain is hard to reach at interstellar distances.** With a ~5% clock advantage, a positive net gain requires $t_\text{task}(1 - f) > 2d/c$. Even a $10^6$-second task breaks even only within ~$2.45 \times 10^{-4}$ pc of Earth. This is physically *true* — light latency dominates at interstellar scale — but it means most server placements show a net loss. To make "wins" common, lower `radius_m` (stronger dilation) or scale distances down.

3. **Two coordinate systems share one 3D scene.** Catalog stars are placed from equatorial coordinates (RA/Dec), while servers use galactic longitude/latitude. Both produce valid Cartesian points, but their axes are not physically aligned, so a server's position does not correspond to the true galactic-frame location of nearby stars. This is cosmetic.

4. **"Relativistic Sync Protocol" is loosely named.** The Near-Future mode models *signal-propagation delay* and event-ordering correction (Lamport-clock territory), **not** relativistic time dilation. The genuine (tiny) Earth–Mars clock difference is correctly ignored. The mechanism is "relativistic" only in that it is bounded by $c$.

5. **Identical hardware is assumed.** The efficiency model assumes a task costs the same number of compute-seconds wherever it runs, measured in that machine's local clock. Differences in actual server performance are out of scope.

## Project Structure

```
chronocloud/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── routers/             # /api/stars, /api/physics/*
│   │   ├── services/physics.py  # 5 pure relativistic math functions
│   │   └── models/schemas.py    # Pydantic request/response models
│   ├── scripts/process_stars.py # HYG CSV → stars.json pipeline
│   ├── data/stars.json          # 8,920 processed stars
│   └── tests/                   # 17 unit tests
└── frontend/
    └── src/
        ├── components/
        │   ├── far-future/      # GalaxyMap, ServerPlacer, MetricsDash
        │   └── near-future/     # LedgerTimeline, DriftCounter, SyncSlider
        ├── hooks/useSimulation.js
        └── data/near-future-ledger.json  # 50 mock transactions
```

## Tests

```bash
cd backend
uv run pytest tests/ -v
```
