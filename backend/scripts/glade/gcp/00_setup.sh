#!/usr/bin/env bash
#
# 00_setup.sh — Phase 2G.1: one-time project setup (idempotent).
#
# Sets the active project, enables required APIs, creates the GCS bucket and
# applies CORS, creates the BigQuery dataset, and creates a least-privilege
# service account. Safe to re-run: every create is guarded by an existence check.
#
# Caller IAM prereqs (you, the human running this) — at minimum:
#   * roles/serviceusage.serviceUsageAdmin   (enable APIs)
#   * roles/storage.admin                    (create bucket, set CORS)
#   * roles/bigquery.admin                   (create dataset)
#   * roles/iam.serviceAccountAdmin          (create service account)
#   * roles/resourcemanager.projectIamAdmin  (grant SA roles, optional)
# Plus: `gcloud auth login`, an active billing account on the project, and the
# Cloud SDK (gcloud, bq, gsutil) installed. See DEPLOY.md.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
load_config
require_cmd gcloud bq gsutil envsubst
require_vars PROJECT_ID REGION BQ_LOCATION BUCKET BQ_DATASET APP_ORIGIN

banner "00_setup — project ${PROJECT_ID}"
cat <<EOF
  This will (idempotently):
    1. set gcloud project          -> ${PROJECT_ID}
    2. enable APIs                  -> storage, bigquery, run, compute, artifactregistry
    3. create GCS bucket           -> gs://${BUCKET} (region ${REGION})
    4. apply bucket CORS           -> allow ${APP_ORIGIN} (GET, HEAD)
    5. create BigQuery dataset     -> ${PROJECT_ID}:${BQ_DATASET} (loc ${BQ_LOCATION})
    6. create service account      -> ${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com
EOF

# --- 1. active project ------------------------------------------------------
info "setting active project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null

# --- 2. enable APIs (enabling an already-enabled API is a no-op) ------------
info "enabling required APIs (idempotent)"
gcloud services enable \
  storage.googleapis.com \
  bigquery.googleapis.com \
  run.googleapis.com \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  --project "${PROJECT_ID}"

# --- 3. GCS bucket ----------------------------------------------------------
if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
  info "bucket gs://${BUCKET} already exists — skipping create"
else
  info "creating bucket gs://${BUCKET} in ${REGION}"
  gsutil mb -p "${PROJECT_ID}" -l "${REGION}" "gs://${BUCKET}"
fi

# --- 4. CORS ----------------------------------------------------------------
# cors.json is a template with ${APP_ORIGIN}; inject the real origin into a temp
# file so the committed template never carries a project-specific value.
info "applying CORS to gs://${BUCKET} (origin ${APP_ORIGIN})"
cors_tmp="$(mktemp)"
trap 'rm -f "${cors_tmp}"' EXIT
APP_ORIGIN="${APP_ORIGIN}" envsubst '${APP_ORIGIN}' \
  < "${GCP_DIR}/cors.json" > "${cors_tmp}"
gsutil cors set "${cors_tmp}" "gs://${BUCKET}"

# --- 5. BigQuery dataset ----------------------------------------------------
if bq --project_id="${PROJECT_ID}" show --dataset "${PROJECT_ID}:${BQ_DATASET}" >/dev/null 2>&1; then
  info "dataset ${PROJECT_ID}:${BQ_DATASET} already exists — skipping create"
else
  info "creating dataset ${PROJECT_ID}:${BQ_DATASET} in ${BQ_LOCATION}"
  bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" mk \
    --dataset \
    --description "Void Ranger Deep Field — GLADE+ catalog" \
    "${PROJECT_ID}:${BQ_DATASET}"
fi

# --- 6. least-privilege service account ------------------------------------
sa_email="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "${sa_email}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  info "service account ${sa_email} already exists — skipping create"
else
  info "creating service account ${sa_email}"
  gcloud iam service-accounts create "${SERVICE_ACCOUNT}" \
    --project "${PROJECT_ID}" \
    --display-name "Void Ranger Deep Field deploy (least privilege)"
fi

# Grant the minimum roles the SA needs for the pipeline (load BQ, read/write the
# asset bucket, run as Cloud Run). Granting an existing binding is idempotent.
info "granting least-privilege roles to ${sa_email}"
for role in roles/bigquery.dataEditor roles/bigquery.jobUser roles/storage.objectAdmin; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member "serviceAccount:${sa_email}" \
    --role "${role}" \
    --condition=None \
    >/dev/null
  info "  granted ${role}"
done

# --- verify -----------------------------------------------------------------
banner "00_setup — verify"
fail=0
gcloud config get-value project 2>/dev/null | grep -qx "${PROJECT_ID}" \
  && info "OK active project = ${PROJECT_ID}" || { err "active project mismatch"; fail=1; }
gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1 \
  && info "OK bucket gs://${BUCKET} present" || { err "bucket missing"; fail=1; }
gsutil cors get "gs://${BUCKET}" | grep -q "${APP_ORIGIN}" \
  && info "OK CORS allows ${APP_ORIGIN}" || { err "CORS not applied"; fail=1; }
bq --project_id="${PROJECT_ID}" show --dataset "${PROJECT_ID}:${BQ_DATASET}" >/dev/null 2>&1 \
  && info "OK dataset ${PROJECT_ID}:${BQ_DATASET} present" || { err "dataset missing"; fail=1; }
gcloud iam service-accounts describe "${sa_email}" --project "${PROJECT_ID}" >/dev/null 2>&1 \
  && info "OK service account ${sa_email} present" || { err "service account missing"; fail=1; }

[[ "${fail}" -eq 0 ]] || die "00_setup verification FAILED — see errors above"
banner "00_setup — DONE. Next: ./10_load_bigquery.sh"
