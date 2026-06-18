import json
import math
from pathlib import Path

import pandas as pd

MAGNITUDE_CUTOFF = 6.5
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data" / "hygdata_v41.csv"
OUTPUT_PATH = BASE_DIR / "data" / "stars.json"

# Main-sequence mass-luminosity relation: L/L_sun = (M/M_sun)^3.5, so
# M/M_sun = (L/L_sun)^(1/3.5). This is a crude estimate — it ignores giants,
# white dwarfs, and binaries — but it is good enough to make void-hunting
# (placing servers far from mass) physically meaningful in the simulation.
MASS_EXPONENT = 1 / 3.5
MASS_MIN_SOLAR = 0.1
MASS_MAX_SOLAR = 50.0
SUN_ABSMAG = 4.83


def estimate_mass_solar(lum: float, absmag: float) -> float:
    if not lum or lum <= 0:
        # Fall back to luminosity from absolute magnitude when lum is missing.
        if pd.isna(absmag):
            return MASS_MIN_SOLAR
        lum = 10 ** ((SUN_ABSMAG - absmag) / 2.5)
    mass = lum ** MASS_EXPONENT
    return max(MASS_MIN_SOLAR, min(MASS_MAX_SOLAR, mass))


def _clean(value) -> str:
    """Trim a catalog cell to a clean string, collapsing internal whitespace."""
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).split())


def designation(row) -> str:
    """A non-proper label for a star: Bayer/Flamsteed, else HD/HIP catalog id."""
    bf = _clean(row.get("bf"))
    if bf:
        return bf
    for col, prefix in (("hd", "HD"), ("hip", "HIP")):
        val = row.get(col)
        if val is not None and not pd.isna(val):
            return f"{prefix} {int(val)}"
    return ""


def process_stars():
    df = pd.read_csv(INPUT_PATH)

    df = df[df["mag"] <= MAGNITUDE_CUTOFF]
    df = df[df["dist"].notna() & (df["dist"] > 0)]

    stars = []
    for _, row in df.iterrows():
        dist = row["dist"]
        ra_rad = row["ra"] * 15 * (math.pi / 180)
        dec_rad = row["dec"] * (math.pi / 180)

        stars.append({
            "x": round(dist * math.cos(dec_rad) * math.cos(ra_rad), 4),
            "y": round(dist * math.cos(dec_rad) * math.sin(ra_rad), 4),
            "z": round(dist * math.sin(dec_rad), 4),
            "size": round(max(0.5, (MAGNITUDE_CUTOFF - row["mag"]) / MAGNITUDE_CUTOFF * 3), 2),
            "m": round(estimate_mass_solar(row.get("lum"), row.get("absmag")), 3),
            # Labels: `name` is the proper name (only ~4% of stars have one) used
            # for the always-on labels; `desig` is the Bayer/Flamsteed-or-catalog
            # fallback shown on hover; `mag` (apparent) ranks brightness; `con`
            # is the constellation abbreviation.
            "name": _clean(row.get("proper")),
            "desig": designation(row),
            "mag": round(float(row["mag"]), 2),
            "con": _clean(row.get("con")),
        })

    with open(OUTPUT_PATH, "w") as f:
        json.dump(stars, f)

    print(f"Wrote {len(stars)} stars to {OUTPUT_PATH}")


if __name__ == "__main__":
    process_stars()
