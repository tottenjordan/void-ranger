# ChronoCloud

An interactive educational web application demonstrating the effects of relativistic computing and time dilation.

## Simulation Modes

- **Interplanetary DevOps** — Synchronize database ledgers between Earth and Mars, dealing with light-speed delay and micro-time drifts. Adjust a relativistic sync protocol slider to correct transaction ordering in real time.
- **Deep-Space Cloud Compute** — Place computational servers in a 3D star field to maximize gravitational time dilation while balancing light-speed communication latency. See real-time efficiency metrics.

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

**Concept:** In a far-future scenario, humanity places computational servers near massive celestial objects to exploit gravitational time dilation. Clocks tick slower in stronger gravitational fields (general relativity), so a server near a dense star could complete days of computation while only hours pass on Earth. The tradeoff: the results must travel back at light speed, and the farther the server, the longer the round-trip delay.

**Features:**
- **3D Galaxy Map** — An interactive star field rendered from the HYG astronomical catalog (8,920 real stars). Rotate, zoom, and pan to explore. Background stars twinkle; data stars are color-coded by luminosity (brighter stars appear warmer).
- **Server Placement** — Click anywhere on the map or enter galactic coordinates (distance, longitude, latitude) to deploy a "Time Sink" server. The server appears as a floating, glowing sphere surrounded by gravitational field rings and sparkles.
- **Light-Speed Communication Line** — A dashed line connects Earth (green marker at origin) to your server, with an animated signal pulse traveling back and forth. The label shows distance in parsecs and round-trip travel time.
- **Metrics Dashboard** — Three cards update in real time with animated value transitions:
  - *Local Server Compute Time* — how long the task takes on the server's dilated clock
  - *Earth Wait Time* — compute time + round-trip light delay
  - *Net Gain/Loss* — whether the dilation benefit outweighs the communication cost
- **Task Duration Control** — Adjust the "Task (s)" input in the header to simulate different workload sizes. Longer tasks benefit more from time dilation.
- **Camera Fly-To** — The camera automatically frames both Earth and the server when you place one.

**What problems does it address?**
- Builds intuition for the competing forces in relativistic computing: gravitational time dilation saves compute time, but light-speed latency adds communication overhead.
- Demonstrates why "closer to a black hole" is not always better — at some distance, the latency cost exceeds the dilation benefit.
- Provides a hands-on way to explore the Schwarzschild metric without equations.

**Try this:** Place a server at 1 parsec, note the Net Gain/Loss, then move it to 100 parsecs. Watch how the latency dominates at large distances. Now increase the task duration to 1,000,000 seconds — at what distance does the dilation benefit finally win?

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
