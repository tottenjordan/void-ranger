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

## Usage

### Deep-Space Compute (default mode)
- Rotate and zoom the 3D star field with your mouse
- Enter galactic coordinates (distance, longitude, latitude) in the "Deploy Time Sink Server" panel and click **Deploy Time Sink**, or click directly on the galaxy map
- The metrics cards below show Local Server Compute Time, Earth Wait Time, and Net Gain/Loss — hover for explanations
- Adjust the **Task (s)** input in the header to change the base computation duration

### Interplanetary DevOps
- Toggle to this mode via the nav bar
- The chart shows Earth (green) vs Mars (orange) transaction timelines offset by light-speed delay
- The **Data Drift Errors** counter shows out-of-order transactions
- Drag the **Relativistic Sync Protocol** slider to compensate — watch the drift errors decrease

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
