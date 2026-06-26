#!/usr/bin/env bash
# Shared helpers for the Void Ranger Deep Field GCP provisioning suite.
#
# Sourced (not executed) by the numbered scripts. Provides:
#   * load_config            — source config.env with a clear error if missing
#   * require_vars           — assert required config keys are set
#   * require_cmd            — assert a CLI (gcloud/bq/gsutil/...) is on PATH
#   * banner / info / warn / err / die  — consistent logging
#   * confirm                — interactive y/N prompt (teardown)
#
# Conventions: every key comes from config.env; nothing is hardcoded.

# Resolve this suite's directory regardless of caller cwd.
GCP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# backend/ is three levels up: gcp/ -> glade/ -> scripts/ -> backend/
BACKEND_DIR="$(cd "${GCP_DIR}/../../.." && pwd)"
# Repo root is one level above backend/; the React app lives in frontend/.
# 30_serve.sh `run` mode builds it and stages frontend/dist -> backend/web.
REPO_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
FRONTEND_DIR="${REPO_ROOT}/frontend"

# --- logging ---------------------------------------------------------------
banner() {
  echo ""
  echo "============================================================"
  echo "  $*"
  echo "============================================================"
}
info() { echo "  [info] $*"; }
warn() { echo "  [warn] $*" >&2; }
err()  { echo "  [error] $*" >&2; }
die()  { err "$*"; exit 1; }

# --- config ----------------------------------------------------------------
# Source config.env from the suite directory. Fail loudly if absent.
load_config() {
  local cfg="${GCP_DIR}/config.env"
  if [[ ! -f "${cfg}" ]]; then
    err "config.env not found at ${cfg}"
    err "Create it from the template, then re-run:"
    err "    cp ${GCP_DIR}/config.env.example ${cfg}"
    err "    \$EDITOR ${cfg}"
    exit 1
  fi
  # shellcheck disable=SC1090  # path is dynamic by design (suite dir)
  source "${cfg}"

  # Apply optional defaults so callers can rely on them being set.
  : "${SERVICE_ACCOUNT:=voidranger-deploy}"
  : "${ASSET_PREFIX:=deepfield}"
  : "${ASSET_CACHE_CONTROL:=public, max-age=31536000, immutable}"
  : "${GLADE_DAT:=./gladep.dat}"

  # Deep Field grid build tuning (optional). GRID_N = voxels per axis (cost ∝ N³;
  # must match the committed grid's 48 to stay byte-identical). GRID_JOBS = worker
  # processes for the parallel build; empty lets build_grid.py auto-pick os.cpu_count().
  : "${GRID_N:=48}"
  : "${GRID_JOBS:=}"

  # Resource label applied to every GCP asset the suite creates whose type
  # supports labels (GCS bucket, BigQuery dataset/tables/view, Cloud Run service,
  # compute global address + forwarding-rule). Single source of truth: override
  # the value via SOLUTION_LABEL in config.env. Some resources have NO labels API
  # (compute backend-bucket, url-map, ssl-certificate, target-https-proxy, and
  # service accounts) and are left untagged — noted where they're created.
  : "${SOLUTION_LABEL:=void-ranger}"
  LABEL_EQ="solution=${SOLUTION_LABEL}"                      # gcloud --labels / --update-labels
  LABEL_COLON="solution:${SOLUTION_LABEL}"                   # bq --label/--set_label, gsutil label ch -l
  LABEL_DDL="labels=[(\"solution\",\"${SOLUTION_LABEL}\")]"  # BigQuery DDL OPTIONS()
}

# require_vars VAR1 VAR2 ... — die if any named var is empty/unset.
require_vars() {
  local missing=0 v
  for v in "$@"; do
    if [[ -z "${!v:-}" ]]; then
      err "required config key '${v}' is empty — set it in config.env"
      missing=1
    fi
  done
  [[ "${missing}" -eq 0 ]] || die "fix config.env and re-run"
}

# require_cmd CMD [CMD...] — die if any CLI is not installed.
require_cmd() {
  local c
  for c in "$@"; do
    command -v "${c}" >/dev/null 2>&1 || \
      die "'${c}' not found on PATH — install the Google Cloud SDK (gcloud, bq, gsutil)"
  done
}

# confirm "message" — interactive y/N. Returns 0 on yes. Used by teardown.
confirm() {
  local prompt="${1:-Are you sure?}" reply
  read -r -p "${prompt} [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]]
}

# The public HTTPS base URL for an object in the bucket (no CDN). Assets are
# world-readable when option (b) is used; with the LB/CDN the user substitutes
# the LB IP/host. Printed by build/serve scripts.
gcs_public_base() {
  echo "https://storage.googleapis.com/${BUCKET}"
}
