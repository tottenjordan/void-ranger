"""Pinning + structural tests for the Deep Field grid builder (scripts/glade/build_grid.py).

Pins current build_grid behavior at small N (N=8 on the committed ~20k-row
sample) so the Phase C optimization refactors stay byte-faithful: the grid must
keep shape (N,N,N), float32 dtype, and finite values. These tiny builds are
cheap and safe to run alongside the production build.
"""
import sys
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.glade import build_grid  # noqa: E402

SAMPLE = BACKEND_DIR / "data" / "samples" / "glade_sample.csv.gz"


def test_build_grid_small_shape_dtype_finite():
    df = build_grid.load_sample(SAMPLE)
    xyz, mass = build_grid.prepare_galaxies(df, 500.0)
    grid = build_grid.build_grid(
        xyz, mass, r_max=500.0, n=8, softening_mpc=0.5, exaggeration=1.0
    )
    assert grid.shape == (8, 8, 8)
    assert grid.dtype == np.float32
    assert np.all(np.isfinite(grid))
