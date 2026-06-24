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
  "CREATE OR REPLACE TABLE \`${PROJECT_ID}.${BQ_DATASET}.${SNAP_TABLE}\`
   OPTIONS(${LABEL_DDL})
   AS
   SELECT * FROM \`${PROJECT_ID}.${BQ_DATASET}.${VIEW}\`"

# --- 2. extract -> GZIP CSV shards in GCS, then assemble one local CSV.gz ----
# BigQuery PARALLELIZES an extract into MULTIPLE gzip shards as soon as the output
# is non-trivial (observed: ~7 shards for the 3.5M-row 500-Mpc subset) — it does
# NOT only shard above 1 GB. The builders read a single --in file, so we extract
# WITHOUT per-shard headers, download every shard, and assemble ONE clean
# single-member gzip with the known header line prepended. Row order across shards
# is irrelevant: build_tiles orders points by brightness and build_grid sums
# contributions order-independently.
expected_header="ra,dec,dist_mpc,b_mag,k_mag,w1_mag,mass_msun,zcmb"
LOCAL_SHARD_DIR="${WORK_DIR}/extract_shards"
rm -rf "${LOCAL_SHARD_DIR}"; mkdir -p "${LOCAL_SHARD_DIR}"

# Clear any stale shards from a previous run first (idempotent).
gsutil -m rm -f "${GS_CSV_PATTERN}" >/dev/null 2>&1 || true
info "extracting ${SNAP_TABLE} -> ${GS_CSV_PATTERN} (headerless shards)"
bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" extract \
  --destination_format=CSV \
  --compression=GZIP \
  --print_header=false \
  "${PROJECT_ID}:${BQ_DATASET}.${SNAP_TABLE}" \
  "${GS_CSV_PATTERN}"

# `|| true` so a zero-object extract (gsutil ls exits non-zero) reaches the
# friendly die below instead of aborting under pipefail with an opaque error.
shard_count="$( { gsutil ls "${GS_CSV_PATTERN}" 2>/dev/null || true; } | wc -l | tr -d ' ')"
[[ "${shard_count}" -ge 1 ]] || die "extract produced no shards at ${GS_CSV_PATTERN}"
info "downloading ${shard_count} shard(s) -> ${LOCAL_SHARD_DIR}"
gsutil -m cp "${GS_CSV_PATTERN}" "${LOCAL_SHARD_DIR}/"

# Assemble ONE single-member gzip: known header line, then every shard body
# (decompressed and recompressed together). A single member is maximally
# compatible with pandas read_csv across all shard counts.
info "assembling ${shard_count} shard(s) -> ${LOCAL_CSV}"
{
  printf '%s\n' "${expected_header}"
  for s in "${LOCAL_SHARD_DIR}"/*.csv.gz; do gzip -dc "${s}"; done
} | gzip -c > "${LOCAL_CSV}"

# Sanity: the first decompressed line must be the builder CSV contract.
# Read just the first line via process substitution so `gzip -dc` isn't killed by
# a `head` SIGPIPE (which under pipefail+set -e would abort the whole script).
IFS= read -r actual_header < <(gzip -dc "${LOCAL_CSV}")
actual_header="${actual_header%$'\r'}"
if [[ "${actual_header}" != "${expected_header}" ]]; then
  die "assembled CSV header mismatch.
  expected: ${expected_header}
  actual:   ${actual_header}
  The glade_usable view SELECT must emit exactly these columns in this order."
fi
info "OK assembled CSV header matches builder contract: ${actual_header}"

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
