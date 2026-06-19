"""Build galaxies.json (the Cosmic Web scale) from the 2MASS Redshift Survey.

Mirrors process_stars.py but at megaparsec scale. Source: 2MRS (Huchra+ 2012),
VizieR catalog J/ApJS/199/26 — ~44,600 galaxies with RA/Dec, K_s magnitude, and
redshift velocity cz. Distance is the Hubble distance d = cz / H0; positions are
Cartesian in Mpc. Galaxy mass is a crude K-band stellar-mass proxy.

The nearest, most recognizable galaxies (Andromeda, M81, Centaurus A, …) have
peculiar-velocity-dominated or negative cz, so the Hubble distance is unreliable
for them. A small curated table anchors those at their literature distances and
gives them proper names — the cosmic-scale parallel to stellar proper names.
"""
import json
import math
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "data" / "galaxies.json"

H0 = 70.0          # km/s/Mpc
M_K_SUN = 3.27     # absolute K magnitude of the Sun
MASS_TO_LIGHT_K = 0.8
MASS_MIN = 1e8
MASS_MAX = 5e12
DIST_MIN_MPC = 0.5   # floor so tiny/peculiar cz doesn't blow up distance/mass
CZ_MAX = 60000.0     # drop sentinels / runaway values

# Curated famous galaxies: name -> (RA deg, Dec deg, distance Mpc). Their cz is
# unreliable (very nearby / blueshifted), so we override distance and name on the
# nearest catalog row. Distances are standard literature values.
FAMOUS = {
    "Andromeda (M31)": (10.6847, 41.2687, 0.78),
    "Triangulum (M33)": (23.4621, 30.6599, 0.86),
    "Bode's Galaxy (M81)": (148.8882, 69.0653, 3.6),
    "Cigar Galaxy (M82)": (148.9685, 69.6797, 3.6),
    "Centaurus A": (201.3651, -43.0191, 3.8),
    "Sculptor Galaxy (NGC 253)": (11.8880, -25.2880, 3.5),
    "Southern Pinwheel (M83)": (204.2538, -29.8654, 4.6),
    "Pinwheel Galaxy (M101)": (210.8025, 54.3491, 6.4),
    "Black Eye Galaxy (M64)": (194.1822, 21.6829, 5.3),
    "Whirlpool Galaxy (M51)": (202.4696, 47.1952, 8.6),
    "Sombrero Galaxy (M104)": (189.9976, -11.6231, 9.55),
    "Virgo A (M87)": (187.7059, 12.3911, 16.4),
    "Fornax A (NGC 1316)": (50.6738, -37.2083, 20.0),
    "Pinwheel (M99)": (184.7067, 14.4164, 16.1),
    "NGC 4565 (Needle)": (189.0863, 25.9876, 11.9),
    "Antennae (NGC 4038)": (180.4709, -18.8689, 22.0),
    "M94": (192.7211, 41.1203, 4.7),
    "M106": (184.7401, 47.3040, 7.4),
}


def k_band_mass(kcmag: float, dist_mpc: float) -> float:
    """Stellar-mass proxy from apparent K magnitude and distance (solar masses)."""
    dist_pc = dist_mpc * 1e6
    abs_k = kcmag - (5 * math.log10(dist_pc) - 5)
    lum_k = 10 ** ((M_K_SUN - abs_k) / 2.5)
    return max(MASS_MIN, min(MASS_MAX, MASS_TO_LIGHT_K * lum_k))


def fetch_2mrs():
    from astroquery.vizier import Vizier

    v = Vizier(columns=["RAJ2000", "DEJ2000", "Kcmag", "cz", "SimbadName"], row_limit=-1)
    return v.get_catalogs("J/ApJS/199/26")[0]


def process_galaxies():
    t = fetch_2mrs()
    ra = np.array(t["RAJ2000"], dtype=float)
    dec = np.array(t["DEJ2000"], dtype=float)
    kc = np.array(t["Kcmag"], dtype=float)
    cz = np.array(t["cz"], dtype=float)
    simbad = [str(s).strip() for s in t["SimbadName"]]

    # Assign curated names/distances to the nearest catalog row for each famous galaxy.
    names = ["" for _ in range(len(ra))]
    dist_override = {}
    for gname, (gra, gdec, gdist) in FAMOUS.items():
        sep2 = (ra - gra) ** 2 + ((dec - gdec) * 1) ** 2  # small-angle, deg²
        j = int(np.argmin(sep2))
        if sep2[j] <= (0.1) ** 2:  # within 0.1°
            names[j] = gname
            dist_override[j] = gdist

    stars = []
    for i in range(len(ra)):
        if i in dist_override:
            dist = dist_override[i]
        else:
            v = cz[i]
            if not np.isfinite(v) or v <= 0 or v > CZ_MAX:
                continue
            dist = max(DIST_MIN_MPC, v / H0)

        if not np.isfinite(kc[i]):
            continue

        ra_rad = math.radians(ra[i])
        dec_rad = math.radians(dec[i])
        stars.append({
            "x": round(dist * math.cos(dec_rad) * math.cos(ra_rad), 4),
            "y": round(dist * math.cos(dec_rad) * math.sin(ra_rad), 4),
            "z": round(dist * math.sin(dec_rad), 4),
            "size": round(max(0.5, (12.0 - kc[i]) / 12.0 * 3), 2),
            "m": round(k_band_mass(kc[i], dist), 1),
            "name": names[i],
            "desig": simbad[i] or f"2MRS {i}",
            "mag": round(float(kc[i]), 2),
            "dist": round(dist, 2),
            "cz": None if not np.isfinite(cz[i]) or cz[i] <= 0 else round(float(cz[i]), 1),
        })

    with open(OUTPUT_PATH, "w") as f:
        json.dump(stars, f)

    named = sum(1 for s in stars if s["name"])
    print(f"Wrote {len(stars)} galaxies ({named} named) to {OUTPUT_PATH}")


if __name__ == "__main__":
    process_galaxies()
