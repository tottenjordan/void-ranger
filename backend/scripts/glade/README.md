# GLADE+ source — Deep Field (Phase 2)

The **Deep Field** scale visualizes the GLADE+ galaxy catalog (~23 M galaxies).
This directory holds the GLADE+ ingest pipeline. Task 2A.1 (this step) documents
the source schema and produces the committed deterministic **sample** that every
later local/CI step builds on — the repo stays **local-first**: build + tests
pass offline with no ~14 GB download and no GCP creds.

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

## Building the Deep Field assets (tiles + grid)

Two builders turn a sample/extract CSV into the two asset families the frontend
streams. Both read the gzipped CSV via `--in` and default to `--source sample`:

```bash
cd backend
uv run python scripts/glade/build_tiles.py --in <csv.gz> --out <dir> --r-max 500
uv run python scripts/glade/build_grid.py  --in <csv.gz> --out <dir> --r-max 500
```

- **`build_tiles.py`** → a sparse **octree** of point tiles (`manifest.json` +
  `*.bin`, 3 float32 x/y/z per galaxy, brightness-ordered). Cheap: the
  full-catalog run (3.54 M usable galaxies) builds in seconds (313 nodes,
  ~61 MB of tiles).
- **`build_grid.py`** → the precomputed **potential grid** (`grid.npy` +
  `grid.json`) the app samples to find the deepest void and the local clock
  advantage without re-summing millions of galaxies. This is the **slow** step
  (see [Build performance](#build-performance--optimization-opportunities)).

### Grid resolution (`--n`)

"Resolution" is **N**, the number of voxels per axis in the potential grid
(`build_grid.py --n`, default **48**). The builder splits the ±`R_MAX` cube
(1000 Mpc wide at `R_MAX = 500`) into an **N × N × N** lattice and computes the
softened Newtonian potential once at each voxel center. `grid.npy` is float32,
so its size is exactly `N³ × 4` bytes.

Because the grid is 3-D, both **cost and file size scale with N³** — the compute
is `voxels × galaxies = N³ × N_galaxies`. Halving N is ~8× cheaper, not 2×:

| N            | voxels   | grid.npy   | cell size | compute vs N=48 |
|--------------|----------|------------|-----------|-----------------|
| 64           | 262,144  | ~1.0 MB    | 15.6 Mpc  | ~2.4× slower    |
| **48** (def) | 110,592  | ~432 KB    | 20.8 Mpc  | 1×              |
| 32           | 32,768   | 128 KB     | 31.3 Mpc  | ~3.4× faster    |
| 24           | 13,824   | ~54 KB     | 41.7 Mpc  | ~8× faster      |

**What lower resolution trades away:** a coarser grid samples the potential
field more bluntly — voids and mass peaks get spatially smeared, so the deepest
void location and the clock-advantage value at a given point are *less spatially
precise*. It does **not** change the physics or the catalog, and it does **not**
affect the rendered galaxy **tiles** (those are built separately and are
unaffected). Resolution only sets the granularity of the precomputed lookup
field — the O(voxels) table that replaces re-summing all galaxies per query.

Guidance: use a **low N (24–32) for fast end-to-end dry runs** that just prove
the pipeline; use **N = 48 (or 64) for an asset you actually ship** so the field
is smooth. The committed sample grid is N=48 deliberately (coarse but under the
~1 MB asset budget).

### Build performance & optimization opportunities

`build_grid.py` is correct and dependency-free but **not optimized for the full
catalog**. Characteristics observed on the real run (3,543,820 galaxies, N=48):

- **Single-core.** The voxel loop runs on one CPU; the full-catalog grid takes
  tens of minutes while 15 other cores sit idle.
- **Oversized chunks → memory-bandwidth bound.** The inner loop processes
  `CHUNK = 256` voxels at a time, forming `CHUNK × N_galaxies` float64
  intermediates (`dx, dy, dz, r`). At 3.54 M galaxies that is ~7 GB *per array*,
  several live at once → ~36 GB RSS, and the run moves on the order of ~15 TB
  through memory across all chunks. The cost is dominated by allocating and
  streaming these big temporaries, not by arithmetic.
- **No progress signal.** Nothing is printed during the voxel loop and
  `grid.npy` is written only at the very end, so there is no partial-file or ETA
  signal while it runs.

For a **teaching asset built once**, this is tolerable — just start it and wait.
If you will **rebuild often**, worthwhile improvements (roughly in order of
effort vs. payoff):

1. **Progress print** — log every K chunks with a running rate/ETA. Trivial, and
   removes the "is it stuck?" uncertainty.
2. **Smaller / adaptive `CHUNK`** — 256 maximizes per-chunk allocation. Pick
   `CHUNK` so `CHUNK × N_galaxies` stays under a target element budget (e.g. a
   few hundred MB). Smaller temporaries improve cache locality and cut RSS by
   ~10×, often *speeding the run up* despite more Python iterations.
3. **Parallelize the voxel loop** — it is embarrassingly parallel; split voxel
   ranges across processes (`multiprocessing.Pool`) for a near-linear speedup on
   a multi-core box. Using float32 throughout (not float64) halves memory
   traffic for free.
4. **Aggregate server-side** — the scalable path for frequent rebuilds is to sum
   the potential in BigQuery (SQL) rather than pulling 13.9 GB and summing on one
   core locally. This is the intent behind `build_grid.load_bq()` /
   `--source bq` (currently a documented `NotImplementedError`; the Phase 2G
   suite materializes the view to CSV and feeds `--in` instead).
5. **Lower N for dry runs** — see [Grid resolution](#grid-resolution---n); N³
   scaling makes this the biggest single lever for a quick pipeline check.
