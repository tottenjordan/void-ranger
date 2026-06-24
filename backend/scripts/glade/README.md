# GLADE+ source — Deep Field (Phase 2)

The **Deep Field** scale visualizes the GLADE+ galaxy catalog (~23 M galaxies).
This directory holds the GLADE+ ingest pipeline. Task 2A.1 (this step) documents
the source schema and produces the committed deterministic **sample** that every
later local/CI step builds on — the repo stays **local-first**: build + tests
pass offline with no 6 GB download and no GCP creds.

Plan: [`docs/plans/003-cosmic-web-phase-2-deep-field.md`](../../../docs/plans/003-cosmic-web-phase-2-deep-field.md)

## Catalog

- **Source:** VizieR catalog `VII/291` (Dálya+ 2022, GLADE+), single table
  `VII/291/gladep`. The full catalog is the fixed-width `gladep.dat`,
  23,181,758 rows.
- **Volume bound:** `R_MAX = 500 Mpc`. The Deep Field is capped to a ±500 Mpc
  cube so the tiles and potential grid stay tractable and meaningful. We keep
  only rows with a **usable luminosity distance** (`f_dL > 0`, `0 < dL ≤ R_MAX`).

## Distance-completeness caveat

Most GLADE+ rows **lack a usable distance** — `dL` is blank and the distance
flag `f_dL` is `0`. We keep only rows with `f_dL > 0` (a measured/usable
luminosity distance) inside the cube. Even so, completeness is magnitude- and
band-dependent: the catalog is roughly complete to **~44 Mpc in the B band** and
**~500 Mpc in W1** (which is why `R_MAX = 500` is a sensible bound — W1
completeness roughly holds there). The sample is therefore a *bright-biased*
slice, not a volume-complete one; that is fine for the visualization and the
potential grid.

## Column map (VizieR `VII/291/gladep`)

Columns we use, with the VizieR alias, the fixed-width `gladep.dat` byte range
(1-based, inclusive, from the VizieR `VII/291` ReadMe), unit, and meaning:

| VizieR alias | `gladep.dat` bytes | label    | unit          | meaning |
|--------------|--------------------|----------|---------------|---------|
| `RAJ2000`    | 135–155            | `RAdeg`  | deg           | Right ascension (J2000) |
| `DEJ2000`    | 157–179            | `DEdeg`  | deg           | Declination (J2000) |
| `Bmag`       | 181–198            | `Bmag`   | mag           | Apparent B magnitude |
| `Kmag`       | 310–327            | `Kmag`   | mag           | Apparent K magnitude |
| `W1mag`      | 348–365            | `W1mag`  | mag           | Apparent WISE W1 magnitude |
| `zcmb`       | 449–471            | `zcmb`   | —             | Redshift (CMB frame) |
| `dL`         | 521–543            | `dL`     | Mpc           | Luminosity distance |
| `f_dL`       | 566                | `f_dL`   | [0/3]         | Distance flag: 0 = no usable distance; >0 = usable |
| `M*`         | 568–577            | `M*`     | 1e10 solMass  | Stellar mass |

Other notable catalog columns not used here: `BMAG` (absolute B), `PGC`/`GLADE+`
identifiers, `zhelio`, per-magnitude errors, `Type`.

## Output schema (`glade_sample.csv.gz`)

Lowercase, numeric, one row per kept galaxy:

| column      | source            | notes |
|-------------|-------------------|-------|
| `ra`        | `RAJ2000` (deg)   | |
| `dec`       | `DEJ2000` (deg)   | |
| `dist_mpc`  | `dL` (Mpc)        | `0 < dist_mpc ≤ R_MAX` |
| `b_mag`     | `Bmag` (mag)      | apparent |
| `k_mag`     | `Kmag` (mag)      | apparent |
| `w1_mag`    | `W1mag` (mag)     | apparent |
| `mass_msun` | `M*` × 1e10       | converted from 1e10 solMass → solar masses |
| `zcmb`      | `zcmb`            | redshift (CMB frame) |

**Brightness for ranking:** later tile/grid builders rank galaxies by apparent
brightness (lowest magnitude = brightest). The canonical ranking magnitude is
**W1**, falling back to **B** then **K** when W1 is missing. Rows missing *all
three* of these are dropped (they have no usable brightness to rank by). All
three magnitude columns are kept in the output so downstream builders can choose.

## Usage

Run with `uv` from `backend/`.

### (a) Sample from VizieR — local dev default

```bash
cd backend
uv run python scripts/glade/sample_glade.py
```

Pulls a bounded slice of `VII/291/gladep` via astroquery with server-side
filters (`dL` in `0..R_MAX`, `f_dL > 0`), keeps `--rows` rows (default
**20000**, kept small so the committed sample is light and CI stays fast), drops
rows missing the ranking magnitude, sorts deterministically by RA then Dec, and
writes the gzipped CSV. **No RNG** — same invocation → byte-identical file.

Options: `--rows N` (default 20000), `--r-max MPC` (default 500),
`--out PATH` (default `backend/data/samples/glade_sample.csv.gz`).

### (b) The real fixed-width `gladep.dat` — full run

```bash
cd backend
uv run python scripts/glade/sample_glade.py --in /path/to/gladep.dat
# or: GLADE_DAT=/path/to/gladep.dat uv run python scripts/glade/sample_glade.py
```

Reads the fixed-width file using the byte offsets above, applies the same
distance filters and deterministic ordering. (This path is exercised later by the
GCP provisioning suite; the committed sample is produced from the VizieR path.)

## Determinism

The output is reproducible: rows are sorted by a stable key (RA, then Dec) with
no random sampling, floats are written with a fixed `%.6f` format, and the gzip
container is written with `mtime=0` and a fixed internal filename. The same
command produces a byte-identical `glade_sample.csv.gz` every run.
