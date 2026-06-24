# 003 — Cosmic Web Phase 2: Deep Field (GLADE+ big-data on GCP)

**Status:** 🚧 **In progress** — backend + pipeline (2A–2D) **and** frontend (2E) **complete**; docs (2F), GCP suite (2G) **remaining**. Expands [002](002-cosmic-web-phase-2-glade-gcp.md) into an executable, task-by-task plan. Builds on [001](001-cosmic-web-option-c.md) (Phase 1, shipped).

> **For Claude:** REQUIRED SUB-SKILL: Use `executing-plans` skill to implement this plan task-by-task.

## Execution status (as of 2026-06-24)

Executed subagent-driven (each task: implementer → spec review → code-quality review → fix loop) on branch `feat/deepfield-phase2`. Not pushed. Full backend suite: **73 passing**.

**✅ Completed (committed):**
- **2A.1** — GLADE+ schema doc + deterministic sampler (`backend/scripts/glade/{README.md,sample_glade.py}` + committed `glade_sample.csv.gz`). _(commit `5c5d8c5`, pre-session)_
- **2B.1** — Octree LOD tile builder `backend/scripts/glade/build_tiles.py` + `test_tiles.py` (per-axis exact partition; endianness round-trip). _(`05c6750`)_
- **2B.2** — Sample tileset committed to `frontend/public/deepfield/tiles/` (root + 2 levels, 408 KB). _(`7fe9699`)_
- **2C.1** — Potential-grid builder `backend/scripts/glade/build_grid.py` + committed sample grid (N=48, raw J/kg). _(`91bcc65`, `e7cd533`)_
- **2C.2** — Grid loader `load_potential_grid` + trilinear `_grid_potential_at` + tests (env-override-safe, dir-keyed cache). _(`90279e1`)_
- **2C.3** — Grid-based `find_deepest_void`/`find_best_spot` deepfield branches + `SCALES["deepfield"]` (grid-backed `local_potential`) + tests. _(`3d3ea4b`)_
- **2D.1** — API: `scale` Literal adds `"deepfield"` (3 request models); router already generic; calibration finalized (`DEEPFIELD_EXAGGERATION=8.0e5` → deepest-void advantage **1.060**, in the 1.05–1.10 band); TestClient `/efficiency` + `/best-void` + `/best-spot` deepfield tests. _(`f321cc2`)_
- **2E.1** — Frontend: `deepfield` entry in `SCALE_UI` + per-scale `scene` constants (single source `SHARED_SCENE`, consumed by `GalaxyMap`) + `assetBase` (`VITE_ASSET_BASE_URL ?? '/deepfield'`) + 3-way toggle; catalog fetch skipped for deepfield. _(`dd7135d`)_
- **2E.2** — Octree LOD streaming renderer `DeepField.jsx` + `GalaxyMap` scale dispatch: streams `manifest.json` + LE-Float32 `.bin` tiles into `<points>`, throttled (4 Hz) bounding-sphere frustum/zoom walk with refine/coarsen **hysteresis**, 300 k point cap (warn on drop), AbortController/mounted-ref cleanup, decode cache + in-flight de-dupe, lightweight Mpc hover; solar/cosmic `StarField` path untouched. _(`3f2499b`)_

**📋 Remaining:**
- **2F.1** — Docs: `docs/deep-field.md`, README "three scales" + Deep Field subsection, `docs/scaling-the-universe.md` (Phase 2 done), plans 002/README status.
- **2G** — Reproducible GCP provisioning suite `backend/scripts/glade/gcp/` (`config.env.example`, `cors.json`, `00_setup.sh`, `10_load_bigquery.sh`, `20_build_assets.sh`, `30_serve.sh`+`Dockerfile`, `99_teardown.sh`, `DEPLOY.md`); idempotent, `bash -n`-clean; user-run, not CI.

**Key locked decisions (carry forward):**
- Grid stores **raw** potential (J/kg); the deepfield **exaggeration lives in `SCALES`** and is applied once in `gravitational_dilation` (uniform with solar/cosmic) — avoids double-exaggeration. `build_grid.py --exaggeration` defaults to 1.0.
- Grid convention (consumed by interp + search): `grid.npy` float32 `(nz,ny,nx)` indexed `[iz,iy,ix]`; `grid.json` `bounds`=cube faces; voxel **center** `center(i)=lo+(i+0.5)*(hi-lo)/n`. Override dir via env `DEEPFIELD_GRID_DIR`.
- Frontend default `assetBase` = `/deepfield` (served from `frontend/public/deepfield/`); tiles at `/deepfield/tiles/`.
- Backend tests run with `PYTHONPATH=. uv run pytest -q` from `backend/` (plain `uv run pytest` may hit a corp mirror in this env).
- 2D.1 received a lightweight orchestrator verification (not the full two-stage subagent review) at the user's stop request — consider a fuller review on resume if desired.

**Goal:** Add a third scale, **Deep Field**, that visualizes the GLADE+ galaxy catalog (~22.5 M galaxies) by streaming precomputed level-of-detail (LOD) tiles, and searches it in O(1) via a precomputed gravitational-potential grid — a real big-data visualization built GCP-ready but runnable locally from committed sample assets.

**Architecture:** A GCP-ready **offline pipeline** (GLADE+ → GCS → BigQuery → octree LOD `.bin` tiles + a 3-D potential voxel grid → GCS/Cloud CDN) plus a **new `deepfield` scale** in the app: the frontend streams tiles directly from a static asset base (CDN in prod, a committed sample folder in dev); the backend physics/void-search read the potential grid instead of summing 22.5 M galaxies. The existing **Solar** and **Cosmic Web (2MRS)** scales are untouched.

**Tech Stack:** Python (pandas/numpy/pyarrow) + BigQuery + GCS + Cloud CDN + Cloud Run; FastAPI + pytest (`uv`); React 19 + R3F/drei/three. `gcloud`/`bq`/`gsutil` for the (documented, later) deploy.

---

## Context

Void Ranger shipped Phase 1 ([001](001-cosmic-web-option-c.md)): a Solar↔Cosmic toggle with 2MRS (~43,510 galaxies) served as one ~7 MB JSON and drawn as a single `<points>` cloud; the void finder sums a softened potential over every object (`O(grid × N)`). That approach can't scale to GLADE+'s 22.5 M galaxies (hundreds of MB payload; per-frame cloud and per-search sum both fall over). Phase 2 adds the three pieces that make big data tractable — **binary LOD tiles**, **streaming**, and a **precomputed potential grid** — as a **separate "Deep Field" scale** so the proven 2MRS path stays fully local and untouched.

**Decisions locked with the user:**

- **Deep Field is a 3rd scale** (Solar Neighborhood → Cosmic Web (2MRS) → Deep Field (GLADE+)); 2MRS stays as-is and 100% local.
- **GCP-ready, local-first:** build + run the pipeline, **commit a small sample** tileset + grid so the repo builds/tests offline. The full GCP path ships as a **complete, idempotent, parameterized provisioning suite** (creates the GCS bucket, BigQuery dataset/tables/views, Cloud CDN, Cloud Run, IAM, **plus teardown**) with a step-by-step `DEPLOY.md` — so **any user can reproduce the deployment from a bare project** — but its execution is the user's later step (not run in CI).
- **Static assets:** the frontend fetches tiles + grid **directly from a static base URL** (GCS+CDN in prod), switchable to a local sample folder via a config flag. The API stays small.

**Reuses from Phase 1 (read these):**

- `frontend/src/components/far-future/FarFutureView.jsx` — `SCALE_UI` registry (`solar`/`cosmic`), `scale` state + top-bar toggle, `placeServer` (POSTs `/efficiency` with `scale`), threads `scale` to `VoidFinder`/`MetricsDash`/`GalaxyMap`. **Add a `deepfield` entry + 3-way toggle.**
- `frontend/src/components/far-future/GalaxyMap.jsx` — `StarField` (`<points>` + labels + hover), `EarthMarker`, `CommLine`, `DistanceLine`, `ServerMarker`, `CameraController`. **Add a streaming loader for `deepfield`; reuse the markers.**
- `backend/app/services/physics.py` — `SCALES` registry + scale-parameterized funcs (`local_potential`, `server_dilation_factor`, `earth_dilation_factor`, `light_latency`, `find_deepest_void`, `find_best_spot`). **Add a `deepfield` scale whose potential/void-search read the grid.**
- `backend/app/services/catalog.py` — cached loaders. **Add a cached potential-grid loader.**
- `backend/app/routers/physics.py` + `models/schemas.py` — `scale` is a `Literal["solar","cosmic"]`; **extend to include `"deepfield"`.**
- `backend/scripts/process_galaxies.py` — the catalog-pipeline pattern to mirror.
- `frontend/vite.config.js` — proxies `/api`→:8000; no env config yet (**add `VITE_ASSET_BASE_URL`**). CI (`.github/workflows/tests.yml`) runs `uv run pytest -q` + `npx vite build` with **no GCP creds** — the committed sample must make both pass offline.

**Catalog facts (GLADE+):** `gladep.dat`, **23,181,758 rows**, VizieR `VII/291` (fixed-width). Columns include RA, Dec, redshift `z` (+ CMB frame), luminosity distance, B-band & W1 magnitudes, stellar mass, and distance-provenance flags; **many rows lack a distance** — keep only rows with a usable luminosity distance. Complete to ~44 Mpc (B) / ~500 Mpc (W1). The exact byte/column layout must be read from the VizieR `VII/291` ReadMe in Task 2A.1.

---

## Binary formats (single source of truth for all tasks)

- **LOD tile** `tiles/<nodeId>.bin`: little-endian **Float32**, interleaved `x,y,z` in **Mpc** (3 floats/galaxy; no header). Brightness ordering is applied at build time so a prefix of a node is a valid downsample.
- **Tile manifest** `tiles/manifest.json`:
  ```json
  { "unit":"Mpc", "root":"0",
    "nodes": { "0": { "bounds":[minx,miny,minz,maxx,maxy,maxz], "count":N, "children":["00","01",…], "file":"0.bin" }, … } }
  ```
- **Potential grid** `grid/grid.npy` (NumPy `float32` array shape `(nz,ny,nx)`, J/kg, **already exaggerated for the deepfield scale**) + sidecar `grid/grid.json`: `{ "bounds":[minx,miny,minz,maxx,maxy,maxz], "shape":[nz,ny,nx], "unit":"Mpc" }`. The backend reads `.npy`; the value at a point is **trilinear-interpolated**.
- **Volume bound:** the Deep Field is capped to a **±R_MAX Mpc** cube (default **R_MAX = 500**, where W1 completeness roughly holds) so the grid and tiles stay tractable and meaningful. Document this bound.

---

## Phase 2A — Ingest GLADE+ → GCS → BigQuery

### Task 2A.1: Document the GLADE+ schema + a deterministic sampler

**Create:** `backend/scripts/glade/README.md` (column map read from VizieR `VII/291` ReadMe: byte offsets for RA, Dec, `z`/`d_L`, B & W1 mag, stellar mass, dist flags) and `backend/scripts/glade/sample_glade.py` — reads `gladep.dat` (path via arg/env), keeps rows with a usable luminosity distance and `d_L ≤ R_MAX`, and writes a **deterministic ~100 k-row** sample `backend/data/samples/glade_sample.csv.gz` (seeded by row stride, no RNG) for local pipeline dev + tests.

- **Verify:** `uv run python scripts/glade/sample_glade.py --in <gladep.dat>` → sample exists, ~100 k rows, has numeric RA/Dec/d_L/mag.
- **Commit:** `chore(glade): document GLADE+ schema + committed 100k sample`

### Task 2A.2: (the GCS upload + BigQuery load live in the provisioning suite)

The GLADE+→GCS upload and the BigQuery table+view are implemented as **`10_load_bigquery.sh`** in the reproducible provisioning suite (**Phase 2G**), so all `gcloud`/`bq`/`gsutil` provisioning is in one cohesive, idempotent place. Nothing here runs in CI — **local pipeline dev (Tasks 2B/2C) runs against the committed `glade_sample.csv.gz`**, and the BigQuery path (`--source bq`) is exercised only when a user runs the suite against their own project.

---

## Phase 2B — Octree LOD tiles

### Task 2B.1: Tiling builder

**Create:** `backend/scripts/glade/build_tiles.py` — input either the BigQuery view (`--source bq`) or the local sample (`--source sample`, default). Recursively space-partition the ±R_MAX cube into an octree (max depth D, cap ≤ C points/node, e.g. C=40 k); within each node keep the **brightest C** (lowest apparent mag) so coarse levels show prominent galaxies; write each node's `x,y,z` as Float32 `tiles/<id>.bin` + `manifest.json` (format above). Output dir via `--out` (default `backend/data/samples/deepfield/tiles/`).

- **Verify:** run on the sample → manifest validates (root present, child ids exist, counts match `.bin` sizes / 12 bytes); total root points ≤ C.
- **Commit:** `feat(glade): octree LOD tile builder + sample tileset`

### Task 2B.2: Commit a tiny sample tileset

Run `build_tiles.py` on the committed sample into `frontend/public/deepfield/` (so dev + `vite build` serve it same-origin) — a small manifest + a handful of `.bin` tiles (root + 1–2 levels, total < ~1 MB). This is the offline asset the frontend uses by default.

- **Commit:** `chore(glade): commit sample deepfield tileset for local dev`

---

## Phase 2C — Potential voxel grid + O(1) void search

### Task 2C.1: Grid builder

**Create:** `backend/scripts/glade/build_grid.py` — voxelize the ±R_MAX cube at resolution N (e.g. N=64), sum the softened galaxy potential per voxel (chunked NumPy over the sample, or a BigQuery aggregation for the full run), apply the deepfield exaggeration, and write `grid.npy` + `grid.json` (format above). Output to `backend/data/samples/deepfield/grid/` and commit the (coarse) sample grid.

- **Verify:** grid loads; min/max finite; the argmin voxel (deepest void) yields `clock_advantage > 1`.
- **Commit:** `feat(glade): potential-grid builder + sample grid`

### Task 2C.2 (TDD): Grid loader + interpolation in the backend

**Files:** `backend/app/services/catalog.py` (add `load_potential_grid(scale)` — `@lru_cache`, reads `grid.npy`+`grid.json`, path from a config/env, default the committed sample); `backend/app/services/physics.py` (add `_grid_potential_at(pts, scale)` trilinear interpolation); `backend/tests/test_deepfield.py`.

- **Step 1 — failing test:** grid loads; `_grid_potential_at` at the grid's min-voxel center ≈ the stored min (within interp tol); out-of-bounds clamps to the edge.
- **Step 2:** run → fail (functions missing). **Step 3:** implement. **Step 4:** pass. **Commit:** `feat(physics): potential-grid loader + trilinear interpolation`

### Task 2C.3 (TDD): Grid-based void search for deepfield

**Files:** `backend/app/services/physics.py` (deepfield branch in `find_deepest_void`/`find_best_spot` that searches the grid — argmin potential for deepest void; per-voxel `task·(1−f_e/f_s) − 2d/c` argmax for best-spot — **O(voxels)**, independent of catalog size); `backend/tests/test_deepfield.py`.

- **Tests:** `find_deepest_void(scale="deepfield")` returns a point inside ±R_MAX with `advantage > 1`; `find_best_spot(huge_task, scale="deepfield")` returns a finite point with positive net gain; results deterministic; **solar + cosmic paths unchanged**.
- **Commit:** `feat(physics): grid-based deepest-void/best-spot for deepfield`

---

## Phase 2D — Backend deepfield scale wiring

### Task 2D.1 (TDD): Register the `deepfield` scale + API

**Files:** `physics.py` `SCALES` (add `deepfield`: `length_m=MPC_M`, `length_km=MPC_KM`, softening tuned for galaxy scale, `exaggeration` calibrated so the deepest-void advantage lands ~1.05–1.10 against the sample grid, `max_well_depth`, and `potential` sourced from the **grid** not a catalog sum); `local_potential`/`earth_dilation_factor`/`server_dilation_factor` use the grid when `scale=="deepfield"`; `models/schemas.py` (`scale: Literal["solar","cosmic","deepfield"]`); `routers/physics.py` (pass through; cosmic/deepfield default radius in Mpc). **No `/api/galaxies`-style JSON for deepfield** — galaxies are tiles; the API only does physics via the grid.

- **Tests:** `/efficiency` with `scale="deepfield"` returns finite metrics using the grid; `earth_dilation_factor("deepfield")` finite in (0,1]; calibration assertion (advantage band). `uv run pytest -q` all green.
- **Commit:** `feat(api): deepfield scale (grid-backed efficiency + void search)`

---

## Phase 2E — Frontend Deep Field scale + streaming renderer

### Task 2E.1: Asset base config + 3-way scale toggle

**Files:** `frontend/src/components/far-future/FarFutureView.jsx`, `frontend/vite.config.js`.

- Add a `deepfield` entry to `SCALE_UI` (`unit:'Mpc'`, `originLabel:'Earth'`, `objectNoun:'galaxy'`, `toggleLabel:'Deep Field'`, `defaultRadius:300`, **plus per-scale scene constants** — a larger background/camera/grid for the ±500 Mpc volume — promote the currently-shared `GalaxyMap` constants into `SCALE_UI`). Add `assetBase: import.meta.env.VITE_ASSET_BASE_URL ?? '/deepfield'`.
- Make the top-bar toggle render all three scales. On switching to `deepfield`: don't fetch `/api/*` for the catalog — hand the streamer the `assetBase`. `placeServer`/finder/metrics already thread `scale` (now `'deepfield'`).
- **Verify:** `npx vite build` clean.
- **Commit:** `feat(fe): Deep Field scale entry + asset-base config + 3-way toggle`

### Task 2E.2: Octree LOD streaming renderer

**Files:** `frontend/src/components/far-future/GalaxyMap.jsx` (+ a new `frontend/src/components/far-future/DeepField.jsx`).

- `DeepField` (rendered inside the rotating group for `deepfield`): fetch `${assetBase}/tiles/manifest.json`; load the root `.bin` into a `<points>` buffer; on camera move (throttled), load visible nodes within the frustum/zoom, merge into the buffer, evict off-screen/over-budget nodes, cap total in-memory points (e.g. ≤ 300 k). Decode `.bin` via `fetch().arrayBuffer()` → `Float32Array`. Reuse `EarthMarker`/`CommLine`/`DistanceLine`/`ServerMarker`/hover. `GalaxyMap` renders `StarField` (solar/cosmic) **or** `DeepField` (deepfield) based on `scale`.
- **Verify:** `npx vite build` clean; (Playwright in Verification).
- **Commit:** `feat(fe): octree LOD streaming renderer for Deep Field`

---

## Phase 2F — Docs

### Task 2F.1: Document Deep Field

**Files:** `docs/cosmic-web.md` or a new `docs/deep-field.md` (GLADE+ catalog, tile/grid formats, the O(1) grid void search, the ±500 Mpc bound, calibration); `README.md` (Overview "three scales", a Deep Field subsection, Architecture diagram: static tiles/grid from GCS/CDN); `docs/scaling-the-universe.md` (Phase 2 → done); `docs/plans/002-*.md` (mark expanded → this plan) and `docs/plans/README.md` status. Link from `docs/README.md`.

- **Commit:** `docs: document the Deep Field (GLADE+) scale + pipeline`

---

## Phase 2G — Reproducible GCP provisioning & deploy (scripts + guide; user-run, not CI)

All provisioning lives in `backend/scripts/glade/gcp/`. Every script is **idempotent** (safe to re-run; guards if a resource already exists), **parameterized** by a single `config.env` (copied from `config.env.example`), prints what it will do, and verifies its result. The goal: a user clones the repo, fills in `config.env`, and runs the numbered scripts to **reproduce the entire deployment from a bare GCP project** — and can tear it all down. Authoring these scripts is in-scope now; **running them is the user's later step** (no GCP creds in CI). Where useful, scripts are checked with `bash -n` (and `shellcheck` if available).

`config.env.example` keys: `PROJECT_ID`, `REGION`, `BQ_LOCATION`, `BUCKET` (assets), `BQ_DATASET`, `APP_ORIGIN` (for CORS), `SERVICE_NAME` (Cloud Run), `R_MAX_MPC`.

### Task 2G.1: Config + project bootstrap — `00_setup.sh`
**Create:** `config.env.example`, `cors.json`, `00_setup.sh`. Idempotently: `gcloud config set project`; **enable APIs** (`storage`, `bigquery`, `run`, `compute` [CDN/LB], `artifactregistry`); create the **GCS bucket** (`gsutil mb -l $REGION`, skip if present); apply **bucket CORS** from `cors.json` (allow `$APP_ORIGIN`, GET/HEAD); create the **BigQuery dataset** (`bq mk --location=$BQ_LOCATION`); create a least-privilege **service account** if needed. Document required caller IAM roles + `gcloud auth login` / billing prereqs.

### Task 2G.2: Ingest + tables — `10_load_bigquery.sh`
Upload `gladep.dat` → `gs://$BUCKET/glade/raw/`; `bq load` `$BQ_DATASET.glade_plus` (explicit schema); create the `glade_usable` **view** (usable `d_L ≤ R_MAX`, derived `x,y,z`/mass/mag). **Verify:** a `COUNT(*)` + distance-percentile query.

### Task 2G.3: Build + upload assets — `20_build_assets.sh`
Run `build_tiles.py --source bq` and `build_grid.py --source bq` against `glade_usable`; `gsutil -m rsync` the full `tiles/` + `grid/` to `gs://$BUCKET/deepfield/` with long `Cache-Control`. Print the resulting public **asset base URL** (for `VITE_ASSET_BASE_URL`).

### Task 2G.4: Serve — `30_serve.sh` (+ optional `Dockerfile`)
Two documented, scripted options: **(a) GCS + Cloud CDN** via an external HTTPS load balancer + `gcloud compute backend-buckets create --enable-cdn` (url-map, cert, forwarding rule — full steps); or **(b)** a simpler public bucket with cache headers (no CDN). If the backend serves the grid, build a `Dockerfile` and `gcloud run deploy $SERVICE_NAME`. Emit the exact `VITE_ASSET_BASE_URL=<cdn-url> npm run build` command for the prod frontend.

### Task 2G.5: Teardown — `99_teardown.sh`
Idempotently remove (with a confirmation prompt) the Cloud Run service, LB/CDN/backend-bucket, bucket contents + bucket, and the BigQuery dataset — so a user can fully clean up and avoid charges.

### Task 2G.6: The reproducible guide — `DEPLOY.md`
`backend/scripts/glade/gcp/DEPLOY.md` — prereqs (gcloud install/auth, billing, IAM roles); copy `config.env`; run `00 → 10 → 20 → 30` in order with **expected output + a verification check at each step**; the prod frontend build with `VITE_ASSET_BASE_URL`; **cost notes** (BigQuery 1 TB/mo free, GCS storage, CDN/egress); and `99_teardown.sh`. Written so it's followable end-to-end on a bare project by someone new to the repo.

**Commit (grouped):** `feat(gcp): reproducible provisioning suite (setup/load/build/serve/teardown) + DEPLOY guide`

---

## Verification (end-to-end, local-first)

1. **Backend:** `cd backend && uv run pytest -q` — green, incl. new `test_deepfield.py` (grid interp, grid void search, deepfield efficiency) and **unchanged solar/cosmic**.
2. **Pipeline (local sample):** `uv run python scripts/glade/build_tiles.py` and `build_grid.py` against `glade_sample.csv.gz` reproduce the committed sample tileset + grid (deterministic).
3. **Frontend:** `cd frontend && npx vite build` clean with the committed `frontend/public/deepfield/` sample.
4. **Playwright smoke** (software WebGL; note the swiftshader white-frame flake — retry/relaunch until the canvas renders dark): toggle to **Deep Field** → tiles stream (coarse root then refinement on zoom); place a node → metrics populate (grid-backed); `find_deepest_void` → advantage > 1; toggle back to Cosmic/Solar → unchanged; zero console errors; screenshot.
5. **No-network guarantee:** with no `VITE_ASSET_BASE_URL` and no GCP, dev + build + tests all pass on the committed sample.
6. **Provisioning suite (reproducibility):** every script in `backend/scripts/glade/gcp/` passes `bash -n` (and `shellcheck` if present); `DEPLOY.md` is followable end-to-end on a bare project; scripts are idempotent (re-running is safe) and `99_teardown.sh` removes everything. The actual GCP run/deploy is the user's later step — **not part of CI**.

---

## Notes / risks

- **Backward compatibility:** solar + cosmic must be byte-for-byte unchanged — keep them as the regression guard (existing tests stay green).
- **Calibration:** the deepfield exaggeration must be re-tuned against the GLADE+ grid (different density/masses than 2MRS); assert the deepest-void advantage band in tests.
- **Volume bound (±500 Mpc):** state it in the UI/docs; it's a tractability + completeness choice, not physics.
- **GLADE+ distance completeness:** most rows lack distances — report the kept count; don't imply full coverage.
- **Binary endianness/dtype:** Float32 little-endian must match between the Python writer and the JS `Float32Array` reader — add a tiny round-trip assertion in the tile builder.
- **Streaming budget:** cap in-memory points and throttle tile loads; log any dropped/over-budget nodes (no silent truncation).
- **Cost guardrails (GCP):** BigQuery 1 TB/month free; the 6 GB table + tiling/grid queries are bounded — log bytes scanned; materialize intermediates to avoid repeated full scans. `DEPLOY.md` states storage/CDN/egress costs and `99_teardown.sh` removes everything.
- **Reproducibility:** provisioning scripts are idempotent + parameterized by `config.env` (no hardcoded project/bucket), use least-privilege IAM, and are ordered (`00→10→20→30`, `99` to tear down) so a newcomer can recreate the deployment from a bare project.
- **lru_cache:** regenerating the grid/catalog needs a backend restart to take effect (seen in Phase 1).
- **Execution:** subagent-driven; land backend (2C/2D, TDD) before the frontend streamer (2E) so the API contract is fixed first.
