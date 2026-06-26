# 004 — Single Cloud Run Service (Option C): serve SPA + API from one origin

**Status:** 📐 **Planned / in progress** (approved 2026-06-24) — branch `feat/single-service-cloudrun`. No PR yet.

**Goal:** Host the Void Ranger frontend on Cloud Run by serving the built React SPA *and* the FastAPI API from a **single** Cloud Run service (one origin, one URL, one deploy), so the existing relative `/api/*` calls work with **zero frontend changes** and no CORS.

**Architecture:** FastAPI mounts the built SPA via `StaticFiles(html=True)` at `/`, behind the existing `/api/*` routers. The frontend is built on the host with `VITE_ASSET_BASE_URL` pointing at the GCS bucket (Deep Field tiles stay on GCS — they're ~61 MB / 313 files and don't belong in the image). The built `dist/` is staged into the backend build context as `backend/web/` and baked into the image. The potential grid continues to be staged from GCS into the image (unchanged). Same-origin ⇒ the API needs no CORS.

**Tech Stack:** FastAPI + Starlette `StaticFiles` (already a dep), uvicorn, `uv`; React 19 + Vite 6 (`npm run build`); bash provisioning suite + Cloud Run / Cloud Build.

---

## Context — why this work exists

The app today has **no turnkey frontend deploy**. `backend/scripts/glade/gcp/30_serve.sh` deploys the **backend** to Cloud Run (`run` mode) and the **Deep Field assets** to GCS/CDN (`public`/`cdn`), but `DEPLOY.md` only says to build `frontend/dist/` and "deploy to your static host" (unspecified). Splitting frontend and backend across two origins also trips a latent bug: `30_serve.sh run` passes `--set-env-vars APP_ORIGIN=…` but `backend/app/main.py` **hardcodes** `allow_origins=["http://localhost:5173"]` and never reads `APP_ORIGIN`, so a separately-hosted frontend would be CORS-blocked.

**Why Option C:** every frontend API call uses a **relative path** (`/api/stars`, `/api/physics/cartesian|efficiency|best-void|best-spot`, `/api/galaxies` — see `ServerPlacer.jsx`, `VoidFinder.jsx`, `FarFutureView.jsx`). Serving the SPA from the same FastAPI service makes those resolve same-origin with no rebuild-time API base and no CORS. It collapses hosting to one Cloud Run service. (Rejected alternative: a hermetic multi-stage Node-in-Docker build with `--source` = repo root — more reproducible but more invasive; the repo's established idiom is host-build + stage-into-context, which `30_serve.sh` already does for the grid + Dockerfile.)

**Intended outcome:** `./30_serve.sh run` produces one Cloud Run URL that serves the full UI at `/` and the API at `/api/*`; Deep Field tiles load from GCS; the orphaned `APP_ORIGIN`/CORS gap is fixed; local dev (`npm run dev` + uvicorn) is unchanged.

---

## Files to change

- `backend/app/main.py` — **primary.** Add a `create_app()` factory: read `APP_ORIGIN` for CORS, move health to `/healthz`, conditionally mount the SPA at `/`.
- `backend/tests/test_web.py` — **new.** TestClient coverage: SPA served at `/`, API still routes, app boots without a web dir.
- `backend/scripts/glade/gcp/Dockerfile` — bake the staged SPA (`COPY web ./web`).
- `backend/scripts/glade/gcp/30_serve.sh` (+ `_lib.sh` for `FRONTEND_DIR`) — `run` mode builds the frontend, stages `dist/` → `backend/web`, extends the cleanup trap, relaxes the `APP_ORIGIN` requirement.
- `.gitignore` — ignore `backend/web/` (the staged build copy).
- `backend/scripts/glade/gcp/DEPLOY.md` (+ brief `README.md` note) — document the single-service path.

**Reuse (do not reinvent):**
- `DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"` (`catalog.py:9`) — mirror this for `WEB_DIR`.
- Existing `TestClient` usage (`tests/test_deepfield.py:336-340`) — same style for the new test (`httpx` is already a dev dep; no new deps).
- The stage-into-context + `trap … rm` + refuse-if-exists idiom already in `30_serve.sh serve_run` (Dockerfile + grid staging) — extend it for `web/`.

---

## Task 1: Backend serves the SPA (factory + mount) — TDD

**Files:** `backend/app/main.py`, `backend/tests/test_web.py` (new)

**Step 1 — failing test** (`test_web.py`): use `fastapi.testclient.TestClient` against an app built by a new `create_app(web_dir=…)` factory.
- `tmp_path` web dir with `index.html` (e.g. `<!doctype html><title>Void Ranger</title>`) and `assets/app.js`.
- Assert `GET /` → 200 and body contains the index HTML; `GET /healthz` → 200 `{"status":"ok"}`; `GET /api/stars` → routes to the API (200, or 404 from the router/data layer — **not** the SPA index); app built with a **non-existent** web dir still imports and serves `/healthz` (no mount, `/` → 404).

**Step 2 — run:** `cd backend && PYTHONPATH=. uv run pytest tests/test_web.py -q` → FAIL (`create_app`/`/healthz` missing).

**Step 3 — implement** in `main.py`:
- `import os`, `from pathlib import Path`, `from fastapi.staticfiles import StaticFiles`.
- `WEB_DIR = Path(os.environ.get("WEB_DIR", Path(__file__).resolve().parent.parent / "web"))` → `/app/web` in the image, `backend/web` locally.
- `def create_app(web_dir: Path = WEB_DIR) -> FastAPI:`
  - `app = FastAPI(title="Void Ranger API")`
  - CORS: `origins = ["http://localhost:5173"]`; `app_origin = os.environ.get("APP_ORIGIN")`; if set, `origins.append(app_origin)`. Keep `allow_credentials/methods/headers`.
  - `app.include_router(physics.router)`; `app.include_router(stars.router)` (**before** the mount, so `/api/*` wins).
  - `@app.get("/healthz")` → `{"status": "ok"}` (moved off `/`).
  - `if web_dir.is_dir(): app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")` (guard keeps local/dev + CI booting with no build).
  - `return app`
- Module level: `app = create_app()` (preserves `from app.main import app` used elsewhere).

**Step 4 — run:** test PASSES. Also `PYTHONPATH=. uv run pytest -q` (whole suite) green — `test_deepfield.py`'s `from app.main import app` + TestClient still works; the `/` health route moving to `/healthz` affects nothing that asserts on `/`.

**Step 5 — commit.**

---

## Task 2: Bake the SPA into the Cloud Run image

**Files:** `backend/scripts/glade/gcp/Dockerfile`

- After `COPY data ./data`, add `COPY web ./web` with a comment: the build context is `backend/`; `30_serve.sh run` stages `frontend/dist` → `backend/web` before the build, and FastAPI serves it at `/` (UI + API one origin). `WEB_DIR` defaults to `/app/web`.
- No new build stage; image stays single-stage Python. (`COPY web` requires `backend/web` to exist at build time — Task 3 always produces it; document this contract in the comment.)

**Commit.**

---

## Task 3: `run` mode builds + stages the frontend

**Files:** `backend/scripts/glade/gcp/_lib.sh`, `backend/scripts/glade/gcp/30_serve.sh`

- `_lib.sh`: add `FRONTEND_DIR` next to `BACKEND_DIR`/`GCP_DIR` (repo-root-relative, e.g. `${REPO_ROOT}/frontend`).
- `serve_run()`:
  - `require_cmd gcloud gsutil npm`.
  - Relax CORS requirement: drop `APP_ORIGIN` from `require_vars` (same-origin needs none); still pass it through only if set (Task 1 appends it when present).
  - Compute the public tiles base (same value `serve_public`/`serve_cdn` print, e.g. `https://storage.googleapis.com/${BUCKET}/${ASSET_PREFIX}`).
  - Refuse-if-exists guard on `${BACKEND_DIR}/web` (mirror the staged-Dockerfile guard).
  - Build: `( cd "${FRONTEND_DIR}" && VITE_ASSET_BASE_URL="${asset_base_url}" npm ci && npm run build )`.
  - Stage: `cp -r "${FRONTEND_DIR}/dist" "${BACKEND_DIR}/web"`.
  - Extend the existing `EXIT` trap to also `rm -rf '${BACKEND_DIR}/web'` (keep Dockerfile + grid cleanup).
  - Keep the existing full-grid staging + `DEEPFIELD_GRID_DIR` logic unchanged.
  - Update the success banner: the `run_url` now serves the **full app** (UI at `/`, API at `/api/*`, health at `/healthz`) — no separate static host needed for this path.

**Verify:** `bash -n 30_serve.sh`; confirm `npm run build`, the `web/` stage, the extended trap, and the `VITE_ASSET_BASE_URL` wiring are present.

**Commit.**

---

## Task 4: Ignore the staged build copy

**Files:** `.gitignore` (root)

- Add `backend/web/` (the staged `dist` copy must never be committed; global `dist/` already ignores `frontend/dist`).

**Commit.**

---

## Task 5: Document the single-service deploy

**Files:** `backend/scripts/glade/gcp/DEPLOY.md`, `README.md` (brief)

- `DEPLOY.md` (`run` section + "Build the production frontend"): document that `./30_serve.sh run` now **builds the SPA and bakes it into the image**, serving UI + API from **one** Cloud Run URL (UI `/`, API `/api/*`, health `/healthz`); Deep Field **tiles load from GCS** via `VITE_ASSET_BASE_URL` (not in the image); **no separate static host** and **no CORS** needed (same-origin); `APP_ORIGIN` is now only for optional split hosting. Note `npm` is required on the deployer's machine and `backend/web/` is staged then cleaned up.
- `README.md`: one line pointing at the single-service Cloud Run path if it documents deployment.

**Commit.**

---

## Task 6: Full verification

- **Backend tests:** `cd backend && PYTHONPATH=. uv run pytest -q` — all green (existing + new `test_web.py`).
- **Local same-origin smoke** (proves Option C end-to-end without GCP):
  ```bash
  cd frontend && VITE_ASSET_BASE_URL=/deepfield npm run build
  rm -rf ../backend/web && cp -r dist ../backend/web
  cd ../backend && WEB_DIR=$PWD/web PYTHONPATH=. uv run uvicorn app.main:app --port 8011 &
  curl -sf localhost:8011/healthz                          # {"status":"ok"}
  curl -sf localhost:8011/ | grep -qi "<!doctype html"     # SPA index
  curl -sf localhost:8011/api/stars | head -c 80           # API same-origin
  # stop uvicorn; rm -rf backend/web (don't commit)
  ```
- **Script lint:** `bash -n backend/scripts/glade/gcp/30_serve.sh`.
- **Frontend build still clean:** `cd frontend && npx vite build`.

---

## Branch & PR

Branch `feat/single-service-cloudrun` off `main` (`ae217f9`). PR body: the single-service Option C design, the relative-`/api` → no-CORS rationale, tiles-stay-on-GCS decision, the `APP_ORIGIN`/CORS fix, and the new `test_web.py`. No attribution trailer.

## Verification summary
- `PYTHONPATH=. uv run pytest -q` (incl. new `test_web.py`) — green.
- Local same-origin smoke: `/` serves SPA, `/api/stars` serves API, `/healthz` ok — one origin.
- `bash -n` on `30_serve.sh`; `run` mode builds + stages + bakes the SPA and sets `VITE_ASSET_BASE_URL`/`DEEPFIELD_GRID_DIR`.
- Docs (DEPLOY.md, README) describe the single Cloud Run service.
