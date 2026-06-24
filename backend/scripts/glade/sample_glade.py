"""Write a deterministic GLADE+ sample for local Deep Field pipeline dev.

Produces a gzipped CSV at ``backend/data/samples/glade_sample.csv.gz`` with the
columns the later tile/grid builders need. Two sources:

* ``--source vizier`` (DEFAULT): pull a bounded GLADE+ slice from VizieR via
  astroquery. Server-side filters keep only rows with a usable luminosity
  distance (``f_dL > 0``) within ``R_MAX`` Mpc. No download of the full 6 GB
  catalog and no GCP creds — the committed sample makes the repo build offline.
* ``--in <gladep.dat>`` (or ``GLADE_DAT`` env): read the real fixed-width
  ``gladep.dat`` (VizieR VII/291). We don't have this file locally, so this path
  is exercised later by the GCP suite; it mirrors the same filtering + ordering.

Output is DETERMINISTIC: no RNG. Rows are sorted by a stable key (RA then Dec)
and floats are written with a fixed format, so the same invocation yields a
byte-identical CSV run-to-run.

See ``backend/scripts/glade/README.md`` and
``docs/plans/003-cosmic-web-phase-2-deep-field.md``.
"""
import argparse
import gzip
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
DEFAULT_OUT = BASE_DIR / "data" / "samples" / "glade_sample.csv.gz"

R_MAX_DEFAULT = 500.0   # Mpc — Deep Field cube bound (±R_MAX)
ROWS_DEFAULT = 20000    # keep the committed sample light

# Catalog id + the columns we actually need (VizieR aliases).
VIZIER_CATALOG = "VII/291/gladep"
VIZIER_COLUMNS = ["RAJ2000", "DEJ2000", "dL", "f_dL", "Bmag", "Kmag", "W1mag", "M*", "zcmb"]

# Output schema (lowercase, numeric). M* is in 1e10 solMass; we convert to solar.
OUTPUT_COLUMNS = ["ra", "dec", "dist_mpc", "b_mag", "k_mag", "w1_mag", "mass_msun", "zcmb"]

# Fixed-width byte ranges (1-based, inclusive) from the VizieR VII/291 ReadMe for
# gladep.dat. Note: in the .dat the coords are RAdeg/DEdeg (VizieR exposes them as
# RAJ2000/DEJ2000). (start, end) — convert to 0-based slices below.
DAT_FIELDS = {
    "ra":     (135, 155),  # RAdeg  deg
    "dec":    (157, 179),  # DEdeg  deg
    "b_mag":  (181, 198),  # Bmag   mag
    "k_mag":  (310, 327),  # Kmag   mag
    "w1_mag": (348, 365),  # W1mag  mag
    "zcmb":   (449, 471),  # zcmb
    "dL":     (521, 543),  # dL     Mpc
    "f_dL":   (566, 566),  # f_dL   [0/3] distance flag
    "Mstar":  (568, 577),  # M*     1e10 solMass
}

# Canonical brightness for ranking (later tile/grid builders rank by this):
# prefer W1, fall back to B then K. Documented in the README.
RANKING_MAGS = ("w1_mag", "b_mag", "k_mag")


def _to_float(series: pd.Series) -> pd.Series:
    """Coerce a column (possibly masked / string) to float with NaN for blanks."""
    return pd.to_numeric(series, errors="coerce")


def fetch_vizier(r_max: float, rows: int) -> pd.DataFrame:
    """Pull a bounded GLADE+ slice from VizieR with server-side distance filters."""
    from astroquery.vizier import Vizier

    v = Vizier(
        columns=VIZIER_COLUMNS,
        column_filters={"dL": f"0..{r_max}", "f_dL": ">0"},
        row_limit=rows,
    )
    result = v.get_catalogs(VIZIER_CATALOG)
    if not result:
        raise RuntimeError(f"VizieR returned no catalog for {VIZIER_CATALOG}")
    t = result[0]

    df = pd.DataFrame({
        "ra":     _to_float(pd.Series(np.asarray(t["RAJ2000"], dtype=object))),
        "dec":    _to_float(pd.Series(np.asarray(t["DEJ2000"], dtype=object))),
        "dist_mpc": _to_float(pd.Series(np.asarray(t["dL"], dtype=object))),
        "f_dL":   _to_float(pd.Series(np.asarray(t["f_dL"], dtype=object))),
        "b_mag":  _to_float(pd.Series(np.asarray(t["Bmag"], dtype=object))),
        "k_mag":  _to_float(pd.Series(np.asarray(t["Kmag"], dtype=object))),
        "w1_mag": _to_float(pd.Series(np.asarray(t["W1mag"], dtype=object))),
        "mass_msun": _to_float(pd.Series(np.asarray(t["M*"], dtype=object))) * 1e10,
        "zcmb":   _to_float(pd.Series(np.asarray(t["zcmb"], dtype=object))),
    })
    return df


def read_gladep_dat(path: Path, r_max: float, rows: int) -> pd.DataFrame:
    """Read the real fixed-width gladep.dat using VizieR VII/291 byte offsets.

    We don't have this file locally; this path is exercised later by the GCP
    suite. Same filtering + deterministic ordering as the vizier path.
    """
    names = list(DAT_FIELDS.keys())
    # pandas read_fwf wants 0-based [start, end) half-open spans.
    colspecs = [(s - 1, e) for (s, e) in DAT_FIELDS.values()]
    df = pd.read_fwf(path, colspecs=colspecs, names=names, dtype=str)

    for col in names:
        df[col] = _to_float(df[col])

    df["mass_msun"] = df["Mstar"] * 1e10
    df = df.rename(columns={"dL": "dist_mpc"})
    return df


def filter_and_shape(df: pd.DataFrame, r_max: float) -> pd.DataFrame:
    """Apply distance/usability filters, drop rows missing the ranking mag, shape."""
    # Usable distance within the cube.
    if "f_dL" in df.columns:
        df = df[df["f_dL"].fillna(0) > 0]
    df = df[df["dist_mpc"].notna() & (df["dist_mpc"] > 0) & (df["dist_mpc"] <= r_max)]

    # Drop rows missing the canonical ranking magnitude (prefer W1, fall back B/K).
    has_rank = pd.Series(False, index=df.index)
    for col in RANKING_MAGS:
        has_rank = has_rank | df[col].notna()
    df = df[has_rank]

    df = df[OUTPUT_COLUMNS].copy()
    return df


def sort_deterministic(df: pd.DataFrame) -> pd.DataFrame:
    """Stable ordering for reproducible output: RA then Dec."""
    return df.sort_values(["ra", "dec"], kind="mergesort").reset_index(drop=True)


def write_csv_gz(df: pd.DataFrame, out: Path) -> None:
    """Write a deterministic gzipped CSV (fixed float format, no mtime in gzip)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    csv_text = df.to_csv(index=False, float_format="%.6f", lineterminator="\n")
    # mtime=0 and a fixed filename header so the gzip container is byte-identical
    # run-to-run regardless of the absolute output path it's written to.
    with open(out, "wb") as raw:
        with gzip.GzipFile(filename="glade_sample.csv", mode="wb", mtime=0, fileobj=raw) as f:
            f.write(csv_text.encode("utf-8"))


def summarize(df: pd.DataFrame, source: str, out: Path) -> None:
    dist = df["dist_mpc"].to_numpy()
    size = out.stat().st_size
    print(f"source:    {source}")
    print(f"rows kept: {len(df)}")
    if len(df):
        print(f"dist_mpc:  min={dist.min():.3f}  median={np.median(dist):.3f}  max={dist.max():.3f}")
    print(f"output:    {out}  ({size:,} bytes)")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Write a deterministic GLADE+ sample CSV.")
    p.add_argument("--source", choices=["vizier", "dat"], default="vizier",
                   help="data source (default: vizier). --in implies dat.")
    p.add_argument("--in", dest="dat_path", default=os.environ.get("GLADE_DAT"),
                   help="path to the real fixed-width gladep.dat (or GLADE_DAT env).")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="output csv.gz path.")
    p.add_argument("--r-max", type=float, default=R_MAX_DEFAULT, help="cube bound in Mpc (default 500).")
    p.add_argument("--rows", type=int, default=ROWS_DEFAULT, help="max rows to pull (default 20000).")
    args = p.parse_args(argv)

    out = Path(args.out)
    r_max = args.r_max

    source = args.source
    if args.dat_path and source == "vizier":
        source = "dat"  # --in implies the fixed-width path

    if source == "dat":
        if not args.dat_path:
            p.error("--source dat requires --in <gladep.dat> (or GLADE_DAT env).")
        dat = Path(args.dat_path)
        if not dat.exists():
            p.error(f"gladep.dat not found: {dat}")
        df = read_gladep_dat(dat, r_max, args.rows)
        df = filter_and_shape(df, r_max)
        df = sort_deterministic(df)
        if len(df) > args.rows:
            df = df.iloc[: args.rows].reset_index(drop=True)
        label = f"dat:{dat}"
    else:
        df = fetch_vizier(r_max, args.rows)
        df = filter_and_shape(df, r_max)
        df = sort_deterministic(df)
        label = f"vizier:{VIZIER_CATALOG}"

    write_csv_gz(df, out)
    summarize(df, label, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
