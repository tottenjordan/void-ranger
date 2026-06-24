#!/usr/bin/env bash
#
# 10_load_bigquery.sh — Phase 2G.2: load GLADE+ into BigQuery (idempotent).
#
# Uploads the raw fixed-width gladep.dat to GCS, loads it into a "raw line" table
# (one STRING column per record), then creates the `glade_usable` VIEW that
# parses the documented VizieR VII/291 byte offsets with SUBSTR, applies the
# usable-distance filter (f_dL > 0, 0 < d_L <= R_MAX_MPC), and emits EXACTLY the
# CSV column contract the local builders read:
#
#     ra, dec, dist_mpc, b_mag, k_mag, w1_mag, mass_msun, zcmb
#
# (matches sample_glade.py OUTPUT_COLUMNS; mass_msun = M* * 1e10). 20_build_assets.sh
# extracts this view to a CSV.gz and feeds it to the builders via --in.
#
# Why "raw line + SUBSTR view" instead of an explicit columnar load?
#   gladep.dat is FIXED-WIDTH; `bq load` has no fixed-width parser. Loading each
#   record as one STRING and parsing byte ranges in SQL (the same 1-based offsets
#   sample_glade.py uses) is the faithful, dependency-free way to get an explicit
#   typed schema out the other side via the view. See DEPLOY.md.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
load_config
require_cmd gcloud bq gsutil
require_vars PROJECT_ID BQ_LOCATION BUCKET BQ_DATASET R_MAX_MPC

RAW_TABLE="glade_raw_line"          # one STRING column: the fixed-width record
PARSED_TABLE="glade_plus"           # typed columns parsed from the raw line
VIEW="glade_usable"                 # filtered + shaped to the builder CSV contract
GS_RAW="gs://${BUCKET}/glade/raw/gladep.dat"

banner "10_load_bigquery — dataset ${PROJECT_ID}:${BQ_DATASET}"
cat <<EOF
  This will (idempotently):
    1. upload ${GLADE_DAT}
              -> ${GS_RAW}
    2. bq load fixed-width records -> ${BQ_DATASET}.${RAW_TABLE} (1 STRING col)
    3. create typed table          -> ${BQ_DATASET}.${PARSED_TABLE} (SUBSTR parse)
    4. create usable view          -> ${BQ_DATASET}.${VIEW} (d_L <= ${R_MAX_MPC} Mpc)
    5. verify                      -> COUNT(*) + distance percentiles
EOF

# --- 1. upload raw gladep.dat ----------------------------------------------
if gsutil -q stat "${GS_RAW}" 2>/dev/null; then
  info "raw catalog already at ${GS_RAW} — skipping upload (delete it to force re-upload)"
else
  [[ -f "${GLADE_DAT}" ]] || die "GLADE_DAT not found: ${GLADE_DAT}
  Download the fixed-width VizieR VII/291 gladep.dat (~6 GB) and set GLADE_DAT in config.env."
  info "uploading ${GLADE_DAT} -> ${GS_RAW} (this is ~6 GB; may take a while)"
  gsutil -o "GSUtil:parallel_composite_upload_threshold=150M" cp "${GLADE_DAT}" "${GS_RAW}"
fi

# --- 2. load fixed-width records as one STRING column -----------------------
# A field delimiter that does not occur in the data ("\b" backspace) makes
# `bq load` treat each whole line as a single column. --replace makes re-runs
# idempotent (the table is rebuilt from the same source).
info "loading raw lines -> ${BQ_DATASET}.${RAW_TABLE} (idempotent --replace)"
bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" load \
  --replace \
  --source_format=CSV \
  --field_delimiter='\b' \
  --quote='' \
  "${BQ_DATASET}.${RAW_TABLE}" \
  "${GS_RAW}" \
  'line:STRING'

# `bq load` has no label flag; tag the raw table after load (idempotent).
bq --project_id="${PROJECT_ID}" update --set_label "${LABEL_COLON}" \
  "${BQ_DATASET}.${RAW_TABLE}" >/dev/null

# --- 3. parse fixed-width byte ranges into a typed table --------------------
# Byte offsets are 1-based inclusive from the VizieR VII/291 ReadMe, identical to
# sample_glade.py DAT_FIELDS. SUBSTR(line, start, len): len = end - start + 1.
#   ra      135..155   dec    157..179   b_mag  181..198
#   k_mag   310..327   w1_mag 348..365   zcmb   449..471
#   dL      521..543   f_dL   566..566   M*     568..577 (1e10 solMass)
# SAFE_CAST yields NULL for blank fields (mirrors pandas to_numeric coerce).
info "creating typed table ${BQ_DATASET}.${PARSED_TABLE} (CREATE OR REPLACE)"
bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" query \
  --use_legacy_sql=false \
  "CREATE OR REPLACE TABLE \`${PROJECT_ID}.${BQ_DATASET}.${PARSED_TABLE}\`
   OPTIONS(${LABEL_DDL})
   AS
   SELECT
     SAFE_CAST(TRIM(SUBSTR(line, 135, 21))  AS FLOAT64) AS ra,
     SAFE_CAST(TRIM(SUBSTR(line, 157, 23))  AS FLOAT64) AS dec,
     SAFE_CAST(TRIM(SUBSTR(line, 181, 18))  AS FLOAT64) AS b_mag,
     SAFE_CAST(TRIM(SUBSTR(line, 310, 18))  AS FLOAT64) AS k_mag,
     SAFE_CAST(TRIM(SUBSTR(line, 348, 18))  AS FLOAT64) AS w1_mag,
     SAFE_CAST(TRIM(SUBSTR(line, 449, 23))  AS FLOAT64) AS zcmb,
     SAFE_CAST(TRIM(SUBSTR(line, 521, 23))  AS FLOAT64) AS dL,
     SAFE_CAST(TRIM(SUBSTR(line, 566, 1))   AS INT64)   AS f_dL,
     SAFE_CAST(TRIM(SUBSTR(line, 568, 10))  AS FLOAT64) AS m_star_1e10
   FROM \`${PROJECT_ID}.${BQ_DATASET}.${RAW_TABLE}\`"

# --- 4. usable view: filter + shape to the builder CSV contract -------------
# Columns + order MUST equal sample_glade.py OUTPUT_COLUMNS so the extracted CSV
# feeds build_tiles.py / build_grid.py --in directly. Keep rows with a usable
# distance (f_dL > 0, 0 < d_L <= R_MAX) and at least one ranking magnitude.
info "creating view ${BQ_DATASET}.${VIEW} (usable, d_L <= ${R_MAX_MPC} Mpc)"
bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" query \
  --use_legacy_sql=false \
  "CREATE OR REPLACE VIEW \`${PROJECT_ID}.${BQ_DATASET}.${VIEW}\`
   OPTIONS(${LABEL_DDL})
   AS
   SELECT
     ra,
     dec,
     dL AS dist_mpc,
     b_mag,
     k_mag,
     w1_mag,
     m_star_1e10 * 1e10 AS mass_msun,
     zcmb
   FROM \`${PROJECT_ID}.${BQ_DATASET}.${PARSED_TABLE}\`
   WHERE f_dL > 0
     AND dL IS NOT NULL AND dL > 0 AND dL <= ${R_MAX_MPC}
     AND (w1_mag IS NOT NULL OR b_mag IS NOT NULL OR k_mag IS NOT NULL)"

# --- 5. verify: COUNT(*) + distance percentiles ----------------------------
banner "10_load_bigquery — verify (COUNT + distance percentiles)"
bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" query \
  --use_legacy_sql=false \
  --format=prettyjson \
  "SELECT
     COUNT(*) AS usable_rows,
     ROUND(MIN(dist_mpc), 3)  AS d_min_mpc,
     ROUND(APPROX_QUANTILES(dist_mpc, 100)[OFFSET(50)], 3) AS d_p50_mpc,
     ROUND(APPROX_QUANTILES(dist_mpc, 100)[OFFSET(95)], 3) AS d_p95_mpc,
     ROUND(MAX(dist_mpc), 3)  AS d_max_mpc
   FROM \`${PROJECT_ID}.${BQ_DATASET}.${VIEW}\`"

# Fail if the view is empty (a load/parse problem would surface here).
row_count="$(bq --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" query \
  --use_legacy_sql=false --format=csv --quiet \
  "SELECT COUNT(*) FROM \`${PROJECT_ID}.${BQ_DATASET}.${VIEW}\`" | tail -n1)"
[[ "${row_count}" =~ ^[0-9]+$ && "${row_count}" -gt 0 ]] \
  || die "view ${VIEW} returned ${row_count} rows — check the load/parse step"
info "OK ${VIEW} has ${row_count} usable rows"

banner "10_load_bigquery — DONE. Next: ./20_build_assets.sh"
