# 001 — Cosmic Web (Option C): reach beyond the solar neighborhood

**Status:** ✅ **Phase 1 shipped** (PR #6, merged to `main` 2026-06-19). Phase 2
(GLADE+ big-data on GCP) is **planned separately** — see
[002](002-cosmic-web-phase-2-glade-gcp.md).

**Goal:** Extend Void Ranger from the solar neighborhood to the **cosmic web** — a
second "scale" where you place a compute node among galaxies and the void finder
points at *real* cosmic voids — while staying a teaching tool and laying a
GCP-ready path to big-data (22.5 M galaxy) visualization.

**Architecture:** A **scale toggle** ("Solar Neighborhood ↔ Cosmic Web") inside
the existing Deep-Space view. Backend physics/void-search became
**scale-parameterized** (same math, different catalog + length unit + softening +
exaggeration). Phase 1 shipped a teaching MVP on the small, distance-complete
**2MRS** catalog (~45 k galaxies, no cloud). Phase 2 scales to **GLADE+** (22.5 M)
via a GCP-ready pipeline, built local-first and deployed later.

Full options analysis that led here: [../scaling-the-universe.md](../scaling-the-universe.md).
Cosmic-scale physics write-up: [../cosmic-web.md](../cosmic-web.md).

---

## Decisions (locked with the user)

- **Option C (cosmic web)**, prioritizing **reach**.
- **Phased:** 2MRS MVP → GLADE+ big-data.
- **GCP-ready but run locally now** (provision/deploy later).
- **Scale toggle in the same view** (not a separate mode/route).

---

## Phase 1 — Cosmic-web MVP on 2MRS — ✅ COMPLETE

| Task | What it did | Status |
|------|-------------|--------|
| 1.1 | `backend/scripts/process_galaxies.py` → `backend/data/galaxies.json` from **2MRS** (VizieR `J/ApJS/199/26`); Mpc Cartesian + K-band mass proxy | ✅ |
| 1.2 | `SCALES` registry + scale-parameterized `physics.py`; `load_galaxies`/`load_galaxy_arrays` in `catalog.py` | ✅ |
| 1.3 | `GET /api/galaxies`; optional `scale: solar\|cosmic` on `/efficiency`, `/best-void`, `/best-spot` | ✅ |
| 1.4 | `test_galaxies.py` + cosmic-scale physics tests; **solar regression** | ✅ |
| 1.5 | Frontend `scale` state + top-bar toggle; `SCALE_UI` config; pc↔Mpc units; galaxy labels | ✅ |
| 1.6 | `docs/cosmic-web.md`, README + GLOSSARY updates | ✅ |
| 1.7 | Verify (pytest + build + Playwright) → PR #6 → merged | ✅ |

### Outcomes & implementation notes (what actually shipped)

- **Catalog:** `galaxies.json` = **43,510 galaxies** (~7.1 MB JSON), **18 named**
  (Andromeda, Centaurus A, Sombrero, …) anchored at literature distances because
  their redshift distance is unreliable; the rest use Hubble distance
  `d = cz/H0` (`H0 = 70`). Median ~120 Mpc, reach ~740 Mpc.
- **Physics calibration:** cosmic `gravity_exaggeration = 1.0e5` (≈55,000× smaller
  than the stellar `5.5e9`); deepest void within 100 Mpc → **clock advantage ≈
  1.05**. Above ~5e5 both Earth and the void saturate the well-depth cap and the
  advantage collapses toward 1.0 — so it sits deliberately low.
- **Backward compatibility:** every scale-parameterized function defaults to
  `scale="solar"` and reproduces the old values exactly (solar canonical:
  `f_earth = 0.92147…`, `find_deepest_void(300) = (-200, -100, 200)`). **Test
  count: 25 → 36.**
- **UX decision:** kept **"Earth" as the origin noun at both scales** (consistent
  with the "Earth Compute/Wait Time" cards); the Milky-Way framing is explained
  in `cosmic-web.md` rather than split across labels.
- **Numeric-range coincidence:** galaxy coords (~120 Mpc median, ~740 max) are
  numerically close to the star ranges (~120 pc, ~560), so the 3D scene constants
  (camera/grid/background/markers) carried over unchanged — only units/labels
  differed.

### Gotchas discovered (carry into future work)

- **Catalog cache:** `catalog.py` uses `@lru_cache`; regenerating `*.json`
  requires a **backend restart** before `/api/stars` / `/api/galaxies` serves the
  new data.
- **`pkill` exit 144** aborts chained bash commands — run kills standalone.
- **Star catalog version:** `process_stars.py` + README Setup are pinned to **HYG
  v4.1** (`hygdata_v41.csv`, download URL verified live). The maintained catalog
  is now v4.2 — an upgrade would change `stars.json` and the pinned solar
  test values, so it's deliberately *not* bundled here.

---

## Phase 2 — GLADE+ big-data on GCP — 📋 MOVED TO 002

The original plan carried a Phase-2 architecture sketch + task outline. It has
been expanded into its own plan: **[002 — Cosmic Web Phase 2: GLADE+ big-data on
Google Cloud](002-cosmic-web-phase-2-glade-gcp.md)**. Summary of intent:

- Scale from 2MRS (~45 k) to **GLADE+** (~22.5 M galaxies).
- **BigQuery** to ingest/filter/downsample → **GCS (+ Cloud CDN)** binary **octree
  LOD tiles** + a **precomputed potential voxel grid** → **Cloud Run** API.
- **Octree LOD streaming** renderer (coarse → refine on zoom).
- Built **local-first** (sample assets committed); GCP provisioning/deploy is a
  later, documented step.
