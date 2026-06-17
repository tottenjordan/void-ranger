# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What Void Ranger is

An interactive educational web app demonstrating relativistic computing and
time dilation, with two modes:

- **Deep-Space Cloud Compute (far-future):** place a compute server in a
  cosmological void (weak gravity → faster local clock) and weigh the
  time-dilation clock advantage against light-speed communication latency.
- **Interplanetary DevOps (near-future):** an Earth–Mars ledger sync where the
  ~750 s light delay scrambles event ordering, corrected by a "Relativistic
  Sync Protocol" slider.

## Stack

- **Backend:** Python ≥3.11, FastAPI + uvicorn, NumPy/pandas. Managed with
  **`uv`** (not pip) — `pyproject.toml` + `uv.lock`.
- **Frontend:** React 19 + Vite 6 + Tailwind CSS 4. Three.js (r170) via
  `@react-three/fiber` 9 / `@react-three/drei` 10 for the galaxy map;
  Chart.js 4 + `react-chartjs-2` for the ledger timeline.

## Commands

Backend (run from `backend/`):

```bash
uv sync --all-extras          # install deps (incl. dev)
uv run uvicorn app.main:app --reload --port 8000   # dev server
uv run pytest -q              # tests
uv run python scripts/process_stars.py             # regenerate data/stars.json
```

Frontend (run from `frontend/`):

```bash
npm install
npm run dev                   # Vite dev server on :5173 (proxies /api -> :8000)
npm run build                 # production build (CI runs `npx vite build`)
```

Both servers must run together: the frontend proxies `/api` to the backend
(see `frontend/vite.config.js`).

## Layout

- `backend/app/main.py` — FastAPI app, CORS, router wiring.
- `backend/app/routers/` — `physics.py` (`/api/physics/cartesian`,
  `/api/physics/efficiency`), `stars.py` (`/api/stars`).
- `backend/app/services/physics.py` — **the core model** (weak-field
  gravitational time dilation, light latency, efficiency).
- `backend/app/services/catalog.py` — cached star-catalog loaders
  (`load_stars`, `load_star_arrays`).
- `backend/app/models/schemas.py` — Pydantic request/response models.
- `backend/scripts/process_stars.py` — builds `data/stars.json` from the HYG
  catalog CSV (adds Cartesian x/y/z + estimated mass `m`).
- `frontend/src/components/far-future/` — `FarFutureView`, `GalaxyMap`
  (Three.js scene), `MetricsDash`, `ServerPlacer`.
- `frontend/src/components/near-future/` — `NearFutureView`, `LedgerTimeline`
  (Chart.js), `SyncSlider`, `DriftCounter`.
- `docs/images/` — README screenshots + `time_dilation_v2.gif` banner.
- `.github/workflows/tests.yml` — CI: backend (uv sync + pytest) and frontend
  (npm ci + vite build).

## Physics conventions (do not silently break)

- Time dilation is **void-favoring**: a server in a deep void runs *faster*
  than Earth (`clock_advantage = f_server / f_earth > 1`); placing it near
  catalog mass slows it (advantage < 1). Do not reframe as "near mass = faster."
- Weak-field factor `f = √(1 + 2Φ/c²)` with a softened Newtonian potential
  `Φ = −Σ GMᵢ/√(r²+ε²)`. Effects are deliberately scaled by
  `GRAVITY_EXAGGERATION` so they're visible — this is a documented teaching
  exaggeration, keep it labeled as such.
- `earth_compute_time = task_seconds × (f_earth / f_server)`;
  light latency = `2d/c`.
- Near-future: Mars events are observed `LIGHT_DELAY` (≈750 s) late;
  `correction = LIGHT_DELAY × syncOffset`, Mars `perceived = timestamp +
  LIGHT_DELAY − correction`.

## Conventions & gotchas

- Use `uv`, never `pip`. `pyproject.toml` pins
  `[[tool.uv.index]] url="https://pypi.org/simple" default=true` so CI and
  external clones resolve against public PyPI (the local machine otherwise
  uses a corp mirror that contaminates `uv.lock` — keep this pin).
- Respect React Rules of Hooks in R3F components: declare hooks before any
  early `return null`.
- `GalaxyMap` disambiguates click (place/move server) vs. drag (orbit) with a
  ~5 px threshold on the pick-plane. Don't regress to a bare `onClick`.
- WebGL may be unavailable in some environments; `GalaxyMap` has a fallback —
  preserve it.
- After physics or API changes, run `uv run pytest -q` and `npx vite build`,
  and keep `README.md` (Physics & Assumptions section) in sync.
