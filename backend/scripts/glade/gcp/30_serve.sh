#!/usr/bin/env bash
#
# 30_serve.sh — Phase 2G.4: expose the Deep Field assets (idempotent).
#
# Two documented serving options for the static assets, plus an optional Cloud
# Run backend. Pick with SERVE_MODE (env or arg):
#
#   SERVE_MODE=public  (default) — make the bucket assets world-readable with
#       cache headers. Simplest; assets served straight from GCS over HTTPS.
#       VITE_ASSET_BASE_URL = https://storage.googleapis.com/$BUCKET/$ASSET_PREFIX
#
#   SERVE_MODE=cdn — external HTTPS load balancer with Cloud CDN in front of the
#       bucket: backend-bucket (--enable-cdn), url-map, managed cert, HTTPS proxy,
#       global forwarding rule. Lowest latency / cacheable at edge. Requires a
#       domain you control (set LB_DOMAIN) for the managed certificate.
#       VITE_ASSET_BASE_URL = https://$LB_DOMAIN/$ASSET_PREFIX
#
#   SERVE_MODE=run — also deploy the FastAPI backend to Cloud Run (uses the
#       Dockerfile in this dir) if you serve the grid/API from the backend rather
#       than static GCS. Independent of the asset serving choice above.
#
# Usage:  ./30_serve.sh [public|cdn|run]    (or set SERVE_MODE in the environment)

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
load_config
require_cmd gcloud gsutil
require_vars PROJECT_ID REGION BUCKET ASSET_PREFIX

SERVE_MODE="${1:-${SERVE_MODE:-public}}"
GS_ASSET_BASE="gs://${BUCKET}/${ASSET_PREFIX}"

# Resource names for the CDN/LB path (parameterized off the bucket name).
BACKEND_BUCKET="${BUCKET}-backend"
URL_MAP="${BUCKET}-urlmap"
HTTPS_PROXY="${BUCKET}-https-proxy"
CERT_NAME="${BUCKET}-cert"
FWD_RULE="${BUCKET}-https-fr"
IP_NAME="${BUCKET}-ip"

# ---------------------------------------------------------------------------
serve_public() {
  banner "30_serve (public) — world-readable bucket assets"
  info "granting public read on gs://${BUCKET} objects"
  # Bucket-level read for allUsers. Idempotent (re-adding a member is a no-op).
  gsutil iam ch allUsers:objectViewer "gs://${BUCKET}"

  asset_base_url="$(gcs_public_base)/${ASSET_PREFIX}"
  info "verifying manifest is reachable"
  gsutil -q stat "${GS_ASSET_BASE}/tiles/manifest.json" 2>/dev/null \
    || die "manifest not found — run ./20_build_assets.sh first"

  banner "30_serve (public) — DONE"
  cat <<EOF
  Assets are public at:
      ${asset_base_url}

  Build the prod frontend with:
      VITE_ASSET_BASE_URL=${asset_base_url} npm run build
EOF
}

# ---------------------------------------------------------------------------
serve_cdn() {
  require_vars LB_DOMAIN
  banner "30_serve (cdn) — external HTTPS LB + Cloud CDN over the bucket"

  # NOTE on labels: only the global address (1) and forwarding-rule (6) below
  # support labels (applied post-create). The backend-bucket, url-map,
  # ssl-certificate, and target-https-proxy have no labels API, so they are
  # created untagged.

  # Assets must be publicly readable for the backend-bucket to serve them.
  info "granting public read on gs://${BUCKET} objects"
  gsutil iam ch allUsers:objectViewer "gs://${BUCKET}"

  # 1) reserved global IP
  if gcloud compute addresses describe "${IP_NAME}" --global --project "${PROJECT_ID}" >/dev/null 2>&1; then
    info "global IP ${IP_NAME} exists — skipping"
  else
    info "reserving global IP ${IP_NAME}"
    gcloud compute addresses create "${IP_NAME}" --global --project "${PROJECT_ID}"
  fi
  lb_ip="$(gcloud compute addresses describe "${IP_NAME}" --global \
    --project "${PROJECT_ID}" --format='value(address)')"
  # addresses support labels only post-create (no --labels at create); idempotent.
  gcloud compute addresses update "${IP_NAME}" --global \
    --project "${PROJECT_ID}" --update-labels="${LABEL_EQ}" >/dev/null

  # 2) backend bucket with CDN enabled
  if gcloud compute backend-buckets describe "${BACKEND_BUCKET}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    info "backend-bucket ${BACKEND_BUCKET} exists — ensuring CDN enabled"
    gcloud compute backend-buckets update "${BACKEND_BUCKET}" \
      --enable-cdn --project "${PROJECT_ID}" >/dev/null
  else
    info "creating backend-bucket ${BACKEND_BUCKET} (--enable-cdn)"
    gcloud compute backend-buckets create "${BACKEND_BUCKET}" \
      --gcs-bucket-name="${BUCKET}" --enable-cdn --project "${PROJECT_ID}"
  fi

  # 3) url-map -> backend bucket
  if gcloud compute url-maps describe "${URL_MAP}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    info "url-map ${URL_MAP} exists — skipping"
  else
    info "creating url-map ${URL_MAP}"
    gcloud compute url-maps create "${URL_MAP}" \
      --default-backend-bucket="${BACKEND_BUCKET}" --project "${PROJECT_ID}"
  fi

  # 4) managed SSL cert for LB_DOMAIN
  if gcloud compute ssl-certificates describe "${CERT_NAME}" --global --project "${PROJECT_ID}" >/dev/null 2>&1; then
    info "ssl-certificate ${CERT_NAME} exists — skipping"
  else
    info "creating managed ssl-certificate ${CERT_NAME} for ${LB_DOMAIN}"
    gcloud compute ssl-certificates create "${CERT_NAME}" \
      --domains="${LB_DOMAIN}" --global --project "${PROJECT_ID}"
  fi

  # 5) HTTPS target proxy
  if gcloud compute target-https-proxies describe "${HTTPS_PROXY}" --global --project "${PROJECT_ID}" >/dev/null 2>&1; then
    info "target-https-proxy ${HTTPS_PROXY} exists — skipping"
  else
    info "creating target-https-proxy ${HTTPS_PROXY}"
    gcloud compute target-https-proxies create "${HTTPS_PROXY}" \
      --url-map="${URL_MAP}" --ssl-certificates="${CERT_NAME}" \
      --global --project "${PROJECT_ID}"
  fi

  # 6) global forwarding rule (443)
  if gcloud compute forwarding-rules describe "${FWD_RULE}" --global --project "${PROJECT_ID}" >/dev/null 2>&1; then
    info "forwarding-rule ${FWD_RULE} exists — skipping"
  else
    info "creating forwarding-rule ${FWD_RULE} -> ${lb_ip}:443"
    gcloud compute forwarding-rules create "${FWD_RULE}" \
      --address="${IP_NAME}" --global \
      --target-https-proxy="${HTTPS_PROXY}" --ports=443 \
      --project "${PROJECT_ID}"
  fi
  # forwarding-rules support labels only post-create (no --labels at create); idempotent.
  gcloud compute forwarding-rules update "${FWD_RULE}" --global \
    --project "${PROJECT_ID}" --update-labels="${LABEL_EQ}" >/dev/null

  asset_base_url="https://${LB_DOMAIN}/${ASSET_PREFIX}"
  banner "30_serve (cdn) — DONE"
  cat <<EOF
  Load balancer IP:  ${lb_ip}
  ACTION REQUIRED:   point an A record for ${LB_DOMAIN} -> ${lb_ip}, then wait
                     for the managed cert to go ACTIVE (can take ~15-60 min):
      gcloud compute ssl-certificates describe ${CERT_NAME} --global \\
        --format='value(managed.status)'

  Once ACTIVE, build the prod frontend with:
      VITE_ASSET_BASE_URL=${asset_base_url} npm run build
EOF
}

# ---------------------------------------------------------------------------
serve_run() {
  require_vars SERVICE_NAME APP_ORIGIN
  require_cmd gcloud gsutil
  banner "30_serve (run) — deploy FastAPI backend to Cloud Run"

  dockerfile="${GCP_DIR}/Dockerfile"
  [[ -f "${dockerfile}" ]] || die "Dockerfile missing at ${dockerfile}"

  # `gcloud run deploy --source` auto-detects a Dockerfile at the ROOT of the
  # source dir (there is no --dockerfile flag). Our Dockerfile lives in this gcp/
  # dir to keep the backend root clean, so stage it at the source root for the
  # build, then remove it (don't clobber an existing one the user may have).
  staged_dockerfile="${BACKEND_DIR}/Dockerfile"
  if [[ -e "${staged_dockerfile}" ]]; then
    die "a Dockerfile already exists at ${staged_dockerfile}; refusing to overwrite.
  Remove it or deploy manually with that one."
  fi

  # Stage the FULL-catalog potential grid from GCS so the backend serves
  # deepfield physics from it (DEEPFIELD_GRID_DIR below). It rides into the image
  # via the Dockerfile's `COPY data ./data`. If the grid isn't in the bucket yet
  # (run ./20_build_assets.sh first), fall back to the committed sample grid that
  # is already baked into the image — the container still boots, just on the
  # coarser sample. The deepfield exaggeration is auto-derived per grid, so the
  # full grid self-calibrates to the teaching band with no manual tuning.
  staged_grid_parent="${BACKEND_DIR}/data/deepfield_prod"
  staged_grid_dir="${staged_grid_parent}/grid"
  deepfield_env=""

  # Clean up both staged paths on exit (Dockerfile + full grid dir).
  # shellcheck disable=SC2064  # expand paths now, intentionally
  trap "rm -f '${staged_dockerfile}'; rm -rf '${staged_grid_parent}'" EXIT

  cp "${dockerfile}" "${staged_dockerfile}"

  rm -rf "${staged_grid_parent}"
  mkdir -p "${staged_grid_dir}"
  if gsutil -q stat "${GS_ASSET_BASE}/grid/grid.npy" 2>/dev/null \
     && gsutil -q stat "${GS_ASSET_BASE}/grid/grid.json" 2>/dev/null; then
    info "staging full-catalog grid from ${GS_ASSET_BASE}/grid for the backend"
    gsutil -q cp "${GS_ASSET_BASE}/grid/grid.npy"  "${staged_grid_dir}/grid.npy"
    gsutil -q cp "${GS_ASSET_BASE}/grid/grid.json" "${staged_grid_dir}/grid.json"
    deepfield_env=",DEEPFIELD_GRID_DIR=/app/data/deepfield_prod/grid"
  else
    warn "full grid not found at ${GS_ASSET_BASE}/grid — backend will use the committed sample grid (run ./20_build_assets.sh to publish the full grid)"
    rm -rf "${staged_grid_parent}"
  fi

  # Deploy from backend/ source; Cloud Build builds the staged Dockerfile. CORS
  # origin passed as an env var so the FastAPI app can allow the deployed frontend.
  # When the full grid was staged, DEEPFIELD_GRID_DIR points the backend at it;
  # otherwise it's unset and the backend loads the in-image committed sample grid.
  info "deploying ${SERVICE_NAME} to Cloud Run in ${REGION}"
  gcloud run deploy "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --source "${BACKEND_DIR}" \
    --allow-unauthenticated \
    --labels "${LABEL_EQ}" \
    --set-env-vars "APP_ORIGIN=${APP_ORIGIN}${deepfield_env}"
  # Note: the container listens on Cloud Run's injected $PORT (Dockerfile CMD),
  # so we don't pass --port; Cloud Run defaults to 8080, which the image honors.

  run_url="$(gcloud run services describe "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" --region "${REGION}" \
    --format='value(status.url)')"
  banner "30_serve (run) — DONE"
  cat <<EOF
  Cloud Run service URL:  ${run_url}
  Health check:           ${run_url}/api/stars   (or your API root)
  Deepfield grid:         ${deepfield_env:+full catalog (DEEPFIELD_GRID_DIR set)}${deepfield_env:-committed sample (in-image default)}
EOF
}

# ---------------------------------------------------------------------------
case "${SERVE_MODE}" in
  public) serve_public ;;
  cdn)    serve_cdn ;;
  run)    serve_run ;;
  *) die "unknown SERVE_MODE '${SERVE_MODE}' — use one of: public | cdn | run" ;;
esac
