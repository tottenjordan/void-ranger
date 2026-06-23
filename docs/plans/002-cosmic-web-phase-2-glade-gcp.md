# 002 — Cosmic Web Phase 2: GLADE+ big-data on Google Cloud

**Status:** 📋 **Planned** (not started). Depends on [001](001-cosmic-web-option-c.md)
(Phase 1, shipped). Expands the Phase-2 outline from 001 into executable detail.

**Goal:** Scale the Cosmic Web from ~45 k 2MRS galaxies to **GLADE+ (~22.5 M
galaxies)** as a real big-data visualization — streamed by level-of-detail and
searched in O(1) via a precomputed potential field — while keeping the repo
runnable locally and staying GCP-deploy-ready.

**Architecture (target):**
```
GLADE+ CSV (~22.5M, ~6 GB) ─> GCS (raw) ─> BigQuery (filter / rank / spatial-bin)
        │                                        │  exports
        │                                        ├─ octree LOD tiles  (Float32 .bin per node)
        │                                        └─ 3-D potential voxel grid (.bin)
        ▼                                        ▼
   one-time batch (local or Cloud Run job)   GCS bucket (+ Cloud CDN) — static, cacheable
                                                 ▼
        Frontend streams coarse→fine tiles by view/zoom (octree LOD)
        Cosmic void finder reads the potential grid → O(1) in catalog size
        FastAPI on Cloud Run for dynamic endpoints (or fully static assets)
```

**Tech stack added:** Google Cloud Storage (+ Cloud CDN), BigQuery, Cloud Run;
Python (pandas/pyarrow/numpy) for tiling; Three.js octree LOD on the frontend.

---

## Context

Phase 1 proved the cosmic-web concept on 2MRS (served as one ~7 MB JSON, drawn as
a single `<points>` cloud). That approach won't scale to 22.5 M galaxies: the
payload would be ~hundreds of MB and the per-frame point cloud + the
`O(grid × N)` void search would both fall over. Phase 2 introduces the three
pieces that make big data tractable: **binary tiles**, **LOD streaming**, and a
**precomputed potential grid**. We keep the repo runnable with a **small sample**
checked in; the full 22.5 M run happens on GCP and the deploy is a documented,
separate step (per the user's "GCP-ready, local-first" choice).

**Reuses from Phase 1:** the `SCALES` registry, `find_deepest_void`/
`find_best_spot` (cosmic), the scale toggle + `SCALE_UI`, and the cosmic units.
GLADE+ becomes an alternate/ě upgraded cosmic catalog source behind the same
toggle.

**Catalog facts (GLADE+):** ~22.5 M galaxies + 750 k quasars; complete to ~44 Mpc
(B-band), brightest out to ~95 Mpc; **not every row has a distance** (a `dist`
flag marks usable ones); ~6 GB CSV from <https://glade.elte.hu/>. We keep only
rows with a usable luminosity distance / redshift.

---

## Open decisions to confirm before starting

1. **Catalog role:** does GLADE+ **replace** 2MRS as the cosmic catalog, or is it
   a **third toggle option** ("Cosmic Web (2MRS)" vs "Deep Field (GLADE+)")?
   *Recommendation:* GLADE+ becomes the cosmic catalog; keep 2MRS as a tiny
   committed fallback for offline/local dev.
2. **GCP project / bucket / region:** use `jts-wrangler` + a bucket like
   `jts-wrangler-staging`? Region for GCS/BigQuery/Cloud Run?
3. **Runtime asset source:** ship binary tiles as **static GCS+CDN** assets the
   frontend fetches directly (simplest, cacheable) vs proxy through the API.
   *Recommendation:* static GCS+CDN; API only for the (small) potential-grid void
   search if we don't do it client-side.
4. **Cost ceiling:** confirm BigQuery scan budget (1 TB/month free; a 6 GB table
   is well under, but tiling queries repeat).

---

## Phase 2A — Data acquisition & ingest

### Task 2A.1: Download GLADE+ and land it in GCS
- Download the GLADE+ catalog (~6 GB) from glade.elte.hu (document the exact file
  + column layout — GLADE+ is fixed-column text; columns include GLADE/PGC/2MASS
  identifiers, RA, Dec, B/J/H/K magnitudes, redshift `z`, luminosity distance
  `d_L`, and a `dist` flag).
- `gsutil cp` to `gs://<bucket>/glade-plus/raw/`. **Commit a small sampled extract**
  (e.g. 50–100 k rows) to `backend/data/samples/glade_sample.csv.gz` for local dev.

### Task 2A.2: Load into BigQuery
- `bq mk` a dataset (e.g. `void_ranger`); `bq load` the CSV into a table with an
  explicit schema. Keep only rows with a usable distance (`dist` flag set /
  positive `d_L`).
- Add derived columns in SQL: Cartesian `x,y,z` in Mpc (from RA/Dec + `d_L`), a
  mass proxy from B- or K-band luminosity, and an apparent magnitude for ranking.
- Sanity-check counts and ranges (`SELECT COUNT(*)`, distance percentiles).

**Verification:** row counts, null/Distance coverage, a few spot-checked famous
galaxies. **Commit:** the load schema + SQL under `backend/scripts/glade/`.

---

## Phase 2B — Octree LOD tiles

### Task 2B.1: Choose tile format + LOD scheme
- **Format:** per-node `Float32Array` of `[x,y,z]` (+ optional `mag`), little-endian
  `.bin`; one file per octree node; a JSON **manifest** mapping node → bounds +
  child pointers + point count.
- **LOD:** root = a brightness-ranked downsample of the whole volume (~50–100 k
  points); each deeper level adds detail within its octant (cap points/node, e.g.
  ≤ 50 k). Brightest-first sampling so coarse levels show the prominent galaxies.

### Task 2B.2: Generate tiles in BigQuery → GCS
- SQL bins galaxies by an octree cell key (Morton code or recursive bounds) per
  level; export each node (e.g. via `EXPORT DATA` to GCS as Parquet, then a small
  Python step → `.bin`, or compute `.bin` directly in a batch job).
- Write the manifest. Upload tiles to `gs://<bucket>/glade-plus/tiles/`.
- **Commit** a tiny generated sample tileset under `backend/data/samples/tiles/`
  for local dev + tests.

**Verification:** manifest validates; sample tiles load + decode to the right
counts; total point budget per visible set is bounded.

---

## Phase 2C — Precomputed potential voxel grid

### Task 2C.1: Build the grid
- One-time job voxelizes the cosmic volume (e.g. a cube of ±R Mpc at N³
  resolution) and sums the softened galaxy potential per voxel (chunked NumPy, or
  BigQuery). Output a binary 3-D grid + a small header (bounds, N, dtype) to GCS;
  commit a coarse sample grid for local dev.

### Task 2C.2: Wire void search to the grid
- Extend cosmic `find_deepest_void`/`find_best_spot` (in `physics.py`) to use the
  grid when present: trilinear-interpolate the potential → min-search / net-gain
  search becomes **O(1) in catalog size** (independent of 22.5 M). Fall back to
  the direct sum (2MRS path) when no grid is configured.

**Verification:** grid-based deepest void ≈ direct-sum result on the sample;
search latency flat as catalog grows; backend tests cover the grid path.

---

## Phase 2D — Streaming renderer (frontend)

### Task 2D.1: Octree LOD loader for the cosmic scale
- In `GalaxyMap` (cosmic scale only), add an octree streamer: load the root tile,
  then for each visible node within the frustum/zoom, fetch+merge its `.bin` into
  the points buffer; evict off-screen/over-budget nodes; cap total in-memory
  points. Source tiles from a config'd base URL (local sample dir now, GCS/CDN
  later). Reuse the existing labels/hover.

**Verification:** `npx vite build` clean; Playwright shows coarse field on load,
detail filling in on zoom, the finder still working, and no console errors —
against the **committed sample** tileset.

---

## Phase 2E — Serving & deploy (later, documented)

### Task 2E.1: Static assets + CDN
- Serve tiles + grid from GCS with Cloud CDN; set cache headers; a config flag
  (`ASSET_BASE_URL`) switches the frontend between local samples and GCS.

### Task 2E.2: Cloud Run API (if needed)
- Containerize the FastAPI backend (`Dockerfile`); deploy to Cloud Run; env config
  for asset URLs. Document `gcloud run deploy`, `gsutil`, `bq` steps in a runbook.
  **Do not provision in repo work** — this is the explicit later step.

---

## Phase 2F — Docs & verification

- Update `docs/scaling-the-universe.md` (Phase 2 → in progress/done) and
  `docs/cosmic-web.md` (GLADE+ catalog, tiling, potential grid, GCP runbook).
- End-to-end local verification on the sample (build + Playwright + backend tests);
  a separate, documented full-scale GCP run.

---

## Risks / notes

- **Distance completeness:** most of GLADE+'s 22.5 M lack reliable distances —
  after filtering, the usable 3-D set is smaller; report the kept count, don't
  imply full coverage.
- **Cost guardrails:** log BigQuery bytes scanned; avoid repeated full-table
  scans (materialize intermediate tables).
- **Coordinate/units consistency** with the Phase-1 cosmic scale (Mpc, origin at
  Earth/Milky Way) so the toggle and metrics stay coherent.
- **Binary endianness / dtype** must match between the Python writer and the JS
  reader (`DataView`/`Float32Array`); add a tiny round-trip test.
- **Local-first guarantee:** the repo must build and run with only the committed
  samples — no network/GCP dependency for `npm run dev` + tests.
- **Execution gate:** when this plan is picked up, run it through Claude Code plan
  mode (ExitPlanMode approval) before writing code, mirroring this document.
