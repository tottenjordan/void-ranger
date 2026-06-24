#!/usr/bin/env bash
#
# 20_build_assets.sh — Phase 2G.3: build Deep Field assets from BigQuery & upload.
#
# Materializes the glade_usable VIEW to a local CSV.gz, runs the octree tile
# builder and the potential-grid builder against that CSV via their existing
# --in flag (NO new Python deps, NO uv.lock change), then rsyncs the full tiles/
# and grid/ to gs://$BUCKET/$ASSET_PREFIX/ with a long Cache-Control. Prints the
# public asset base URL for VITE_ASSET_BASE_URL.
#
# Why CSV materialization (not a BigQuery Python client)?
#   build_tiles.py / build_grid.py read a gzipped CSV with columns
#   ra,dec,dist_mpc,b_mag,k_mag,w1_mag,mass_msun,zcmb. The glade_usable view emits
#   exactly those columns/order, so `bq extract` -> CSV.gz -> --in is a drop-in.
#   Adding google-cloud-bigquery would force a uv.lock regeneration that the
#   repo forbids. See DEPLOY.md ("Why CSV materialization...").

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
load_config
require_cmd gcloud bq gsutil uv
require_vars PROJECT_ID BQ_LOCATION BUCKET BQ_DATASET R_MAX_MPC

VIEW="glade_usable"
# bq extract cannot extract a VIEW directly, so we first snapshot it to a table.
SNAP_TABLE="glade_usable_snapshot"
# Extract to a wildcard path: BigQuery shards an extract that would exceed ~1 GB
# per file. The usable 500-Mpc subset is small (a few M rows × 8 floats), so we
# expect exactly ONE shard; we assert that below and fail clearly otherwise.
GS_CSV_PREFIX="gs://${BUCKET}/glade/extract"
GS_CSV_PATTERN="${GS_CSV_PREFIX}/${VIEW}-*.csv.gz"

# Local working dirs (under backend/data, mirroring the sample layout).
WORK_DIR="${BACKEND_DIR}/data/deepfield_build"
LOCAL_CSV="${WORK_DIR}/${VIEW}.csv.gz"
TILES_DIR="${WORK_DIR}/deepfield/tiles"
GRID_DIR="${WORK_DIR}/deepfield/grid"
GS_ASSET_BASE="gs://${BUCKET}/${ASSET_PREFIX}"

banner "20_build_assets — view ${PROJECT_ID}:${BQ_DATASET}.${VIEW}"
cat <<EOF
  This will:
    1. snapshot view  -> ${BQ_DATASET}.${SNAP_TABLE}
    2. bq extract     -> ${GS_CSV_PATTERN}  (then copy local)
    3. build tiles    -> ${TILES_DIR}
    4. build grid     -> ${GRID_DIR}
    5. rsync assets   -> ${GS_ASSET_BASE}/{tiles,grid} (Cache-Control: ${ASSET_CACHE_CONTROL})
EOF

mkdir -p "${WORK_DIR}"

# --- 1. snapshot the view to a concrete table (idempotent --replace) --------
info "snapshotting ${VIEW} -> ${BQ_DATASET}.${SNAP_TABLE}"
bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" query \
  --use_legacy_sql=false \
  "CREATE OR REPLACE TABLE \`${PROJECT_ID}.${BQ_DATASET}.${SNAP_TABLE}\` AS
   SELECT * FROM \`${PROJECT_ID}.${BQ_DATASET}.${VIEW}\`"

# --- 2. extract -> GZIP CSV in GCS, then copy local -------------------------
# Column header order is preserved from the table, which matches the builder CSV
# contract. GZIP keeps the transfer + local file small; pandas reads .gz directly.
# Clear any stale shards from a previous run first (idempotent).
gsutil -m rm -f "${GS_CSV_PATTERN}" >/dev/null 2>&1 || true
info "extracting ${SNAP_TABLE} -> ${GS_CSV_PATTERN}"
bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" extract \
  --destination_format=CSV \
  --compression=GZIP \
  --print_header=true \
  "${PROJECT_ID}:${BQ_DATASET}.${SNAP_TABLE}" \
  "${GS_CSV_PATTERN}"

# Assert a single shard. The builders take ONE --in file; BQ only shards when the
# output would exceed ~1 GB/file (not expected for the 500-Mpc subset). If it
# sharded, lower R_MAX_MPC or extend this script to concatenate shards.
# `|| true` so a zero-object extract (gsutil ls exits non-zero) reaches the
# friendly die below instead of aborting under pipefail with an opaque error.
shard_count="$( { gsutil ls "${GS_CSV_PATTERN}" 2>/dev/null || true; } | wc -l | tr -d ' ')"
[[ "${shard_count}" -ge 1 ]] || die "extract produced no shards at ${GS_CSV_PATTERN}"
[[ "${shard_count}" -eq 1 ]] || die "extract sharded into ${shard_count} files \
(>1 GB). The builders read a single --in file. Lower R_MAX_MPC, or concatenate \
the shards (stripping repeated headers) before building."
gs_shard="$(gsutil ls "${GS_CSV_PATTERN}")"
info "copying ${gs_shard} -> ${LOCAL_CSV}"
gsutil cp "${gs_shard}" "${LOCAL_CSV}"

# Sanity: the header must match the builder CSV contract exactly.
# Read just the first line via process substitution so `gzip -dc` isn't killed by
# a `head` SIGPIPE (which under pipefail+set -e would abort the whole script
# before the builders run). Strip a trailing CR if present.
expected_header="ra,dec,dist_mpc,b_mag,k_mag,w1_mag,mass_msun,zcmb"
IFS= read -r actual_header < <(gzip -dc "${LOCAL_CSV}")
actual_header="${actual_header%$'\r'}"
if [[ "${actual_header}" != "${expected_header}" ]]; then
  die "CSV header mismatch.
  expected: ${expected_header}
  actual:   ${actual_header}
  The glade_usable view SELECT must emit exactly these columns in this order."
fi
info "OK CSV header matches builder contract: ${actual_header}"

# --- 3 & 4. run the builders against the extracted CSV via --in -------------
# Run from backend/ so `uv run` resolves the project env. The builders default to
# --source sample and read the gzipped CSV passed to --in.
info "building octree tiles (build_tiles.py --in ${LOCAL_CSV})"
( cd "${BACKEND_DIR}" && uv run python scripts/glade/build_tiles.py \
    --in "${LOCAL_CSV}" \
    --out "${TILES_DIR}" \
    --r-max "${R_MAX_MPC}" )

info "building potential grid (build_grid.py --in ${LOCAL_CSV})"
( cd "${BACKEND_DIR}" && uv run python scripts/glade/build_grid.py \
    --in "${LOCAL_CSV}" \
    --out "${GRID_DIR}" \
    --r-max "${R_MAX_MPC}" )

# --- 5. upload assets with long Cache-Control -------------------------------
# -d makes rsync delete remote files no longer present locally (true mirror), so
# re-runs are idempotent. -m parallelizes. Cache-Control is set on upload.
info "uploading tiles -> ${GS_ASSET_BASE}/tiles"
gsutil -m -h "Cache-Control:${ASSET_CACHE_CONTROL}" rsync -r -d \
  "${TILES_DIR}" "${GS_ASSET_BASE}/tiles"

info "uploading grid -> ${GS_ASSET_BASE}/grid"
gsutil -m -h "Cache-Control:${ASSET_CACHE_CONTROL}" rsync -r -d \
  "${GRID_DIR}" "${GS_ASSET_BASE}/grid"

# --- verify -----------------------------------------------------------------
banner "20_build_assets — verify"
fail=0
for f in tiles/manifest.json grid/grid.json grid/grid.npy; do
  if gsutil -q stat "${GS_ASSET_BASE}/${f}" 2>/dev/null; then
    info "OK ${GS_ASSET_BASE}/${f}"
  else
    err "MISSING ${GS_ASSET_BASE}/${f}"
    fail=1
  fi
done
[[ "${fail}" -eq 0 ]] || die "20_build_assets verification FAILED — see errors above"

asset_base_url="$(gcs_public_base)/${ASSET_PREFIX}"
banner "20_build_assets — DONE"
cat <<EOF
  Public asset base (direct GCS, no CDN):
      ${asset_base_url}

  Use this as VITE_ASSET_BASE_URL for the prod frontend build, OR run
  ./30_serve.sh to put Cloud CDN in front and get a cached HTTPS URL.

  Manifest:  ${asset_base_url}/tiles/manifest.json
  Grid:      ${asset_base_url}/grid/grid.json

  Next: ./30_serve.sh
EOF
