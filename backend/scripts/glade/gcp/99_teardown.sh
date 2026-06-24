#!/usr/bin/env bash
#
# 99_teardown.sh — Phase 2G.5: tear down everything the suite created (idempotent).
#
# Prompts for confirmation, then removes (each guarded by an existence check so a
# partial teardown can be re-run safely):
#   * Cloud Run service        (SERVICE_NAME)
#   * LB / CDN / backend-bucket (forwarding rule, https proxy, cert, url-map,
#                                backend-bucket, reserved IP)
#   * bucket contents + bucket  (gs://BUCKET)
#   * BigQuery dataset          (BQ_DATASET, with all tables/views)
#
# Pass --yes to skip the prompt (e.g. CI cleanup). DESTRUCTIVE — data is deleted.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
load_config
require_cmd gcloud bq gsutil
require_vars PROJECT_ID REGION BUCKET BQ_DATASET

ASSUME_YES=0
[[ "${1:-}" == "--yes" ]] && ASSUME_YES=1

# CDN/LB resource names — must match those created in 30_serve.sh.
BACKEND_BUCKET="${BUCKET}-backend"
URL_MAP="${BUCKET}-urlmap"
HTTPS_PROXY="${BUCKET}-https-proxy"
CERT_NAME="${BUCKET}-cert"
FWD_RULE="${BUCKET}-https-fr"
IP_NAME="${BUCKET}-ip"

banner "99_teardown — DESTRUCTIVE"
cat <<EOF
  About to DELETE in project ${PROJECT_ID}:
    * Cloud Run service   : ${SERVICE_NAME:-<unset>} (region ${REGION})
    * LB/CDN resources    : ${FWD_RULE}, ${HTTPS_PROXY}, ${CERT_NAME},
                            ${URL_MAP}, ${BACKEND_BUCKET}, ${IP_NAME}
    * GCS bucket + objects: gs://${BUCKET}
    * BigQuery dataset    : ${PROJECT_ID}:${BQ_DATASET} (all tables/views)

  This cannot be undone.
EOF

if [[ "${ASSUME_YES}" -ne 1 ]]; then
  confirm "Delete all of the above?" || die "aborted by user (no changes made)"
fi

# Helper: run a delete only if the describe succeeds (resource exists).
# usage: del_if_exists "<label>" "<describe cmd...>" -- "<delete cmd...>"
# (kept simple/inline below instead — each block guards itself.)

# --- Cloud Run service ------------------------------------------------------
if [[ -n "${SERVICE_NAME:-}" ]]; then
  if gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" >/dev/null 2>&1; then
    info "deleting Cloud Run service ${SERVICE_NAME}"
    gcloud run services delete "${SERVICE_NAME}" \
      --project "${PROJECT_ID}" --region "${REGION}" --quiet
  else
    info "Cloud Run service ${SERVICE_NAME} not found — skipping"
  fi
fi

# --- LB / CDN (delete in dependency order: fr -> proxy -> cert/url-map -> bb -> ip) ---
if gcloud compute forwarding-rules describe "${FWD_RULE}" --global --project "${PROJECT_ID}" >/dev/null 2>&1; then
  info "deleting forwarding-rule ${FWD_RULE}"
  gcloud compute forwarding-rules delete "${FWD_RULE}" --global --project "${PROJECT_ID}" --quiet
else
  info "forwarding-rule ${FWD_RULE} not found — skipping"
fi

if gcloud compute target-https-proxies describe "${HTTPS_PROXY}" --global --project "${PROJECT_ID}" >/dev/null 2>&1; then
  info "deleting target-https-proxy ${HTTPS_PROXY}"
  gcloud compute target-https-proxies delete "${HTTPS_PROXY}" --global --project "${PROJECT_ID}" --quiet
else
  info "target-https-proxy ${HTTPS_PROXY} not found — skipping"
fi

if gcloud compute ssl-certificates describe "${CERT_NAME}" --global --project "${PROJECT_ID}" >/dev/null 2>&1; then
  info "deleting ssl-certificate ${CERT_NAME}"
  gcloud compute ssl-certificates delete "${CERT_NAME}" --global --project "${PROJECT_ID}" --quiet
else
  info "ssl-certificate ${CERT_NAME} not found — skipping"
fi

if gcloud compute url-maps describe "${URL_MAP}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  info "deleting url-map ${URL_MAP}"
  gcloud compute url-maps delete "${URL_MAP}" --project "${PROJECT_ID}" --quiet
else
  info "url-map ${URL_MAP} not found — skipping"
fi

if gcloud compute backend-buckets describe "${BACKEND_BUCKET}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  info "deleting backend-bucket ${BACKEND_BUCKET}"
  gcloud compute backend-buckets delete "${BACKEND_BUCKET}" --project "${PROJECT_ID}" --quiet
else
  info "backend-bucket ${BACKEND_BUCKET} not found — skipping"
fi

if gcloud compute addresses describe "${IP_NAME}" --global --project "${PROJECT_ID}" >/dev/null 2>&1; then
  info "releasing global IP ${IP_NAME}"
  gcloud compute addresses delete "${IP_NAME}" --global --project "${PROJECT_ID}" --quiet
else
  info "global IP ${IP_NAME} not found — skipping"
fi

# --- GCS bucket (objects + bucket) -----------------------------------------
if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
  info "deleting bucket gs://${BUCKET} and all objects"
  # `gsutil rm -r` on the bucket removes objects then the bucket itself.
  gsutil -m rm -r "gs://${BUCKET}"
else
  info "bucket gs://${BUCKET} not found — skipping"
fi

# --- BigQuery dataset (all tables/views) -----------------------------------
if bq --project_id="${PROJECT_ID}" show --dataset "${PROJECT_ID}:${BQ_DATASET}" >/dev/null 2>&1; then
  info "deleting BigQuery dataset ${PROJECT_ID}:${BQ_DATASET} (recursive)"
  bq --project_id="${PROJECT_ID}" rm -r -f --dataset "${PROJECT_ID}:${BQ_DATASET}"
else
  info "dataset ${PROJECT_ID}:${BQ_DATASET} not found — skipping"
fi

# --- verify -----------------------------------------------------------------
banner "99_teardown — verify"
fail=0
gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1 \
  && { err "bucket gs://${BUCKET} still present"; fail=1; } \
  || info "OK bucket gone"
bq --project_id="${PROJECT_ID}" show --dataset "${PROJECT_ID}:${BQ_DATASET}" >/dev/null 2>&1 \
  && { err "dataset ${BQ_DATASET} still present"; fail=1; } \
  || info "OK dataset gone"
if [[ -n "${SERVICE_NAME:-}" ]]; then
  gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" >/dev/null 2>&1 \
    && { err "Cloud Run service ${SERVICE_NAME} still present"; fail=1; } \
    || info "OK Cloud Run service gone"
fi

[[ "${fail}" -eq 0 ]] || die "99_teardown verification FAILED — some resources remain"
banner "99_teardown — DONE. The service account and enabled APIs are left intact
  (they incur no cost idle). Remove the SA manually if desired:
    gcloud iam service-accounts delete ${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
