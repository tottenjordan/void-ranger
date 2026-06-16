import json
import math
from pathlib import Path

import pandas as pd

MAGNITUDE_CUTOFF = 6.5
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data" / "hygdata_v41.csv"
OUTPUT_PATH = BASE_DIR / "data" / "stars.json"

1
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
        })

    with open(OUTPUT_PATH, "w") as f:
        json.dump(stars, f)

    print(f"Wrote {len(stars)} stars to {OUTPUT_PATH}")


if __name__ == "__main__":
    process_stars()
