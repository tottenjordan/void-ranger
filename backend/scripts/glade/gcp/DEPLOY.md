# Void Ranger — Deep Field GCP deploy guide (Phase 2G)

This guide takes a **bare GCP project** to a fully deployed Deep Field: the
GLADE+ catalog loaded into BigQuery, precomputed octree tiles + a potential grid
built and uploaded to Cloud Storage, and the assets served (optionally behind
Cloud CDN). Everything is reproducible from numbered, idempotent shell scripts in
this directory and is parameterized by a single `config.env`.

The scripts are **authored to be run by you, later** — they are not executed in
CI and need GCP credentials. Run them in order: **00 → 10 → 20 → 30**, with a
`99` teardown when you're done.

All scripts live in `backend/scripts/glade/gcp/`. Run them from that directory.

```
00_setup.sh         project + APIs + bucket + CORS + dataset + service account
10_load_bigquery.sh upload gladep.dat, load it, create the glade_usable view
20_build_assets.sh  materialize view -> CSV.gz -> build tiles+grid -> upload
30_serve.sh         expose assets (public bucket | Cloud CDN | Cloud Run)
99_teardown.sh      delete everything (confirmation prompt)
_lib.sh             shared helpers (sourced, not run directly)
config.env.example  copy to config.env and fill in
cors.json           CORS template (origin injected from config.env)
Dockerfile          optional Cloud Run image for the FastAPI backend
```

---

## 0. Prerequisites

1. **Google Cloud SDK** installed: `gcloud`, `bq`, `gsutil` on your `PATH`.
   - Install: <https://cloud.google.com/sdk/docs/install>
   - `gnu gettext` for `envsubst` (used to inject the CORS origin) — preinstalled
     on most Linux/macOS; otherwise `apt-get install gettext` / `brew install gettext`.
2. **Authenticate** and set application-default credentials:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```
3. **Billing** must be enabled on the project (BigQuery loads, GCS, CDN, Cloud
   Run all require an active billing account).
4. **Caller IAM roles** — the human running `00_setup.sh` needs at least:
   - `roles/serviceusage.serviceUsageAdmin` — enable APIs
   - `roles/storage.admin` — create bucket, set CORS, set public IAM
   - `roles/bigquery.admin` — create dataset, load, create views
   - `roles/iam.serviceAccountAdmin` — create the service account
   - `roles/resourcemanager.projectIamAdmin` — grant the SA its roles
   - For `30_serve.sh cdn`: `roles/compute.loadBalancerAdmin` (+ `compute.networkAdmin`)
   - For `30_serve.sh run`: `roles/run.admin` and `roles/cloudbuild.builds.editor`
   (`roles/owner` covers all of these if you're the project owner.)
5. **The GLADE+ catalog** — download the fixed-width `gladep.dat` (VizieR
   `VII/291`, ~23.2M rows, ~14 GB). This is **not committed**. Point `GLADE_DAT`
   in `config.env` at it. (Local/CI builds use the committed
   `backend/data/samples/glade_sample.csv.gz` instead and do not need this.)

---

## 1. Configure

```bash
cd backend/scripts/glade/gcp
cp config.env.example config.env
$EDITOR config.env          # fill in PROJECT_ID, BUCKET (globally unique), etc.
```

Required keys: `PROJECT_ID`, `REGION`, `BQ_LOCATION`, `BUCKET`, `BQ_DATASET`,
`APP_ORIGIN`, `SERVICE_NAME`, `R_MAX_MPC`. Optional keys (have defaults):
`GLADE_DAT`, `SERVICE_ACCOUNT`, `ASSET_PREFIX`, `ASSET_CACHE_CONTROL`,
`SOLUTION_LABEL`, `GRID_N`, `GRID_JOBS`.

`config.env` is git-ignored — it carries your project-specific values. Nothing is
hardcoded in the scripts; change everything from this one file.

### Resource labels

Every GCP resource the suite creates whose type supports labels is tagged
**`solution=void-ranger`** (override the value via `SOLUTION_LABEL` in
`config.env`) so you can find, group, and break down billing for all Void Ranger
assets. Labeled: the GCS bucket, the BigQuery dataset + `glade_raw_line` /
`glade_plus` tables + `glade_usable` view + `glade_usable_snapshot`, the Cloud Run
service, and the CDN path's global address + forwarding-rule. Not labeled (no
labels API in GCP): compute backend-bucket, url-map, ssl-certificate,
target-https-proxy, and the service account. Find everything later with, e.g.:

```bash
gcloud compute addresses list --filter="labels.solution=void-ranger"
bq ls --filter "labels.solution:void-ranger" "${PROJECT_ID}:${BQ_DATASET}"
gcloud storage buckets describe gs://$BUCKET --format='value(labels)'
```

---

## 2. `00_setup.sh` — project setup

```bash
./00_setup.sh
```

Idempotently: sets the active project, enables APIs (`storage`, `bigquery`,
`run`, `compute`, `artifactregistry`), creates the GCS bucket, applies CORS from
`cors.json` (allowing `$APP_ORIGIN` for GET/HEAD), creates the BigQuery dataset,
and creates a least-privilege service account.

**Expected output (tail):**
```
  [info] OK active project = <PROJECT_ID>
  [info] OK bucket gs://<BUCKET> present
  [info] OK CORS allows <APP_ORIGIN>
  [info] OK dataset <PROJECT_ID>:<BQ_DATASET> present
  [info] OK service account <SA>@<PROJECT_ID>.iam.gserviceaccount.com present
============================================================
  00_setup — DONE. Next: ./10_load_bigquery.sh
```

**Verify manually (optional):**
```bash
gsutil cors get gs://<BUCKET>
bq show --dataset <PROJECT_ID>:<BQ_DATASET>
```

Re-running is safe: existing resources are detected and skipped.

---

## 3. `10_load_bigquery.sh` — load GLADE+ into BigQuery

```bash
./10_load_bigquery.sh
```

Uploads `gladep.dat` to `gs://$BUCKET/glade/raw/`, loads each fixed-width record
as one `STRING` column (`glade_raw_line`), parses the documented VizieR byte
offsets with `SUBSTR` into a typed table (`glade_plus`), then creates the
`glade_usable` **view**: usable distance (`f_dL > 0`, `0 < d_L ≤ R_MAX_MPC`),
with columns shaped to exactly the builder CSV contract (see the box below).

**Expected output (tail):** a pretty-printed row with `usable_rows`,
`d_min_mpc`, `d_p50_mpc`, `d_p95_mpc`, `d_max_mpc`, then:
```
  [info] OK glade_usable has <N> usable rows
============================================================
  10_load_bigquery — DONE. Next: ./20_build_assets.sh
```

**Verify manually (optional):**
```bash
bq query --use_legacy_sql=false \
  "SELECT * FROM \`<PROJECT_ID>.<BQ_DATASET>.glade_usable\` LIMIT 5"
```
You should see numeric `ra, dec, dist_mpc, b_mag, k_mag, w1_mag, mass_msun, zcmb`.

---

## 4. `20_build_assets.sh` — build & upload Deep Field assets

```bash
./20_build_assets.sh
```

Snapshots the view to a table, `bq extract`s it to `gs://$BUCKET/glade/extract/`
as **GZIP CSV shards**, downloads them, and **assembles one clean single-member
gzip** locally (BigQuery parallelizes the extract into multiple shards — ~7 for
the 3.5 M-row 500 Mpc subset — so the script extracts them *headerless* and
prepends the known header; row order across shards is irrelevant). It then runs
`build_tiles.py` and `build_grid.py` against that CSV via `--in` and
`gsutil -m rsync`es the full `tiles/` + `grid/` to `gs://$BUCKET/$ASSET_PREFIX/`
with a long `Cache-Control`.

After assembly, the script asserts the CSV header equals
`ra,dec,dist_mpc,b_mag,k_mag,w1_mag,mass_msun,zcmb` — a hard guard that the view
matches what the builders read.

> **Build time, resolution & parallelism.** `build_tiles.py` is fast (seconds).
> `build_grid.py` is the slow step but is now **multi-core with live progress**:
> it splits the voxel loop across `GRID_JOBS` worker processes (blank = all
> cores) and streams a rate/ETA to stderr (this script always passes
> `--progress`). On a 16-core box the full-catalog grid (3.5 M galaxies, default
> N=48) builds in roughly an hour — about **8–10× faster** than the old
> single-core path (~8–9 h). Tune resolution with `GRID_N` (cost scales as N³;
> e.g. `GRID_N=32` is ~3.4× cheaper for a quick end-to-end check). See
> **[`../README.md`](../README.md)** → *Grid resolution* and *Build performance*
> for the full trade-off table.
>
> **Rebuilds are bit-identical → no re-upload.** `grid.npy` is byte-identical
> regardless of `GRID_JOBS` / `--chunk` / `--progress`: the parallel path only
> splits *which* voxels each core computes, the per-voxel galaxy sum is unchanged,
> and the float32 cast happens once at the end (proven by
> `build_grid.py` and `tests/test_build_grid_perf.py::test_matches_committed_sample_grid`).
> So regenerating a grid from the same catalog produces the same bytes and
> **never requires a new upload** — `gsutil -m rsync` sees no change.

**Expected output (tail):**
```
  [info] OK gs://<BUCKET>/<ASSET_PREFIX>/tiles/manifest.json
  [info] OK gs://<BUCKET>/<ASSET_PREFIX>/grid/grid.json
  [info] OK gs://<BUCKET>/<ASSET_PREFIX>/grid/grid.npy
============================================================
  20_build_assets — DONE
  Public asset base (direct GCS, no CDN):
      https://storage.googleapis.com/<BUCKET>/<ASSET_PREFIX>
  ...
  Next: ./30_serve.sh
```

**Verify manually (optional):**
```bash
gsutil ls -L gs://<BUCKET>/<ASSET_PREFIX>/tiles/manifest.json   # shows Cache-Control
```

### Why CSV materialization, not a BigQuery client dependency

The plan's first sketch said "run the builders with `--source bq`". We do **not**
do that. Implementing a real BigQuery read in the Python builders would require
adding `google-cloud-bigquery` to `pyproject.toml`, which regenerates `uv.lock`
against this machine's corp PyPI mirror — explicitly forbidden by `CLAUDE.md`
(the lockfile must resolve against public PyPI for external clones/CI).

Instead, the `bq` **CLI** materializes the `glade_usable` view to a `CSV.gz`, and
the builders consume it through their **existing** `--in` flag (the same path the
committed sample uses). The view's `SELECT` emits exactly the columns the
builders' `pd.read_csv` expects — so the extract is a drop-in. No new Python
deps, no `uv.lock` churn, fully reproducible. The `load_bq()` stubs in the two
builders document this and point here.

---

## 5. `30_serve.sh` — expose the assets

Pick a mode (default `public`):

```bash
./30_serve.sh public   # world-readable bucket + cache headers (simplest)
./30_serve.sh cdn      # external HTTPS load balancer + Cloud CDN (needs LB_DOMAIN)
./30_serve.sh run      # also deploy the FastAPI backend to Cloud Run
```

- **public** — `gsutil iam ch allUsers:objectViewer`. Assets served straight from
  GCS over HTTPS. `VITE_ASSET_BASE_URL = https://storage.googleapis.com/$BUCKET/$ASSET_PREFIX`.
- **cdn** — reserves a global IP, creates a CDN-enabled backend-bucket, url-map,
  managed cert, HTTPS proxy, and forwarding rule. Set `LB_DOMAIN` in `config.env`
  (a domain you control); after the run, point an `A` record at the printed IP
  and wait for the managed cert to go `ACTIVE`.
  `VITE_ASSET_BASE_URL = https://$LB_DOMAIN/$ASSET_PREFIX`.
- **run** — deploys the backend via `gcloud run deploy $SERVICE_NAME --source
  backend/`. There is no `--dockerfile` flag, so the script temporarily stages
  this dir's `Dockerfile` at the backend root for the build and removes it after.
  Only needed if you serve the grid/API from the backend rather than static GCS.
  - **Deepfield physics from the full-catalog grid.** In `run` mode the backend
    serves deepfield physics from the **full-catalog** potential grid: the script
    fetches `gs://$BUCKET/$ASSET_PREFIX/grid/{grid.npy,grid.json}` (staging it
    into `data/deepfield_prod/grid` so it rides into the image via the Dockerfile's
    `COPY data ./data`) and sets `DEEPFIELD_GRID_DIR=/app/data/deepfield_prod/grid`
    on the Cloud Run service. This is the consumer that makes the uploaded
    `grid.npy` a **live asset** — previously the bucket grid was an orphan (only
    the tiles were consumed, by the frontend).
  - **Fallback to the in-image sample.** The committed N=48 **sample** grid stays
    the in-image default, so the container boots even if `DEEPFIELD_GRID_DIR` is
    unset or the full grid hasn't been published yet. If the grid isn't in the
    bucket, the script warns and deploys without the env var (run
    `./20_build_assets.sh` first to publish the full grid).
  - **No manual tuning.** The deepfield exaggeration is **auto-derived per grid**
    (closed-form, targeting clock advantage ≈ 1.06), so the full grid
    self-calibrates to the teaching band with no manual re-tuning when you switch
    from the sample to the full catalog.
  - **Lean upload.** A `backend/.gcloudignore` (denylist) keeps the `--source`
    build context small — it excludes `.git/`, `__pycache__/`, `.pytest_cache/`,
    `.venv/`, `tests/`, and the multi-GB local `data/deepfield_build/`, while
    `app/`, `data/samples/`, the staged `data/deepfield_prod/grid`,
    `pyproject.toml`, and `uv.lock` all ride along.

### Build the production frontend

Use the asset base URL the chosen mode printed:

```bash
cd frontend
# public bucket:
VITE_ASSET_BASE_URL=https://storage.googleapis.com/<BUCKET>/<ASSET_PREFIX> npm run build
# or, with CDN:
VITE_ASSET_BASE_URL=https://<LB_DOMAIN>/<ASSET_PREFIX> npm run build
```

Deploy the resulting `frontend/dist/` to your static host. Ensure that host's
origin matches `APP_ORIGIN` in `config.env` (it drives the bucket CORS allow).

---

## 6. Cost notes

- **BigQuery** — storage is billed per GB-month; **query** has a 1 TB/month free
  tier. The load is a one-time job; the `glade_usable` view + the one snapshot
  table + a single full-table extract scan well under 1 TB. Drop the raw/snapshot
  tables after building if you want to minimize storage:
  ```bash
  bq rm -f -t <PROJECT_ID>:<BQ_DATASET>.glade_raw_line
  bq rm -f -t <PROJECT_ID>:<BQ_DATASET>.glade_usable_snapshot
  ```
- **Cloud Storage** — ~14 GB raw `gladep.dat` + the built assets (tiles + grid are
  small, well under a few hundred MB). Standard storage in one region is a few
  cents/GB-month. Delete the raw object after the BigQuery load if you don't need
  to reload: `gsutil rm gs://<BUCKET>/glade/raw/gladep.dat`.
- **Cloud CDN / egress** — egress to the internet and CDN cache fill are billed
  per GB; cache hits are cheaper than origin reads. The long `Cache-Control`
  (immutable, 1 year) maximizes cache hits. Costs scale with traffic.
- **Cloud Run** — scales to zero; you pay only for request time. Negligible when
  idle.

The `99_teardown.sh` script removes the billable resources.

`20_build_assets.sh` writes a transient local working dir at
`backend/data/deepfield_build/` (the extracted CSV + the built tiles/grid before
upload). It is safe to delete after a successful run and should not be committed:
```bash
rm -rf backend/data/deepfield_build
```

---

## 7. `99_teardown.sh` — tear it all down

```bash
./99_teardown.sh          # prompts for confirmation
./99_teardown.sh --yes    # skip the prompt (e.g. scripted cleanup)
```

Idempotently deletes (after confirmation): the Cloud Run service, the LB/CDN
stack (forwarding rule, HTTPS proxy, cert, url-map, backend-bucket, reserved IP),
the bucket and all its objects, and the BigQuery dataset (all tables + views).
The enabled APIs and the service account are left intact (no idle cost); remove
the SA manually if you want a truly bare project — the script prints the command.

---

## Troubleshooting

- **`config.env not found`** — you skipped step 1; `cp config.env.example config.env`.
- **`required config key '<X>' is empty`** — fill that key in `config.env`.
- **`'gcloud'/'bq'/'gsutil' not found`** — install/PATH the Cloud SDK.
- **`GLADE_DAT not found`** — download `gladep.dat` and set `GLADE_DAT`.
- **`CSV header mismatch` (step 20)** — the `glade_usable` view's `SELECT` was
  edited away from the builder contract; restore the column list/order in
  `10_load_bigquery.sh` to `ra, dec, dist_mpc, b_mag, k_mag, w1_mag, mass_msun, zcmb`.
- **Bucket name taken** — `BUCKET` must be **globally** unique; pick another.
- **Managed cert stuck PROVISIONING** — the `A` record for `LB_DOMAIN` isn't
  resolving to the LB IP yet; fix DNS and wait (can take up to ~60 min).
