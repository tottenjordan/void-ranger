"""Pinning + structural tests for the Deep Field grid builder (scripts/glade/build_grid.py).

Pins current build_grid behavior at small N (N=8 on the committed ~20k-row
sample) so the Phase C optimization refactors stay byte-faithful: the grid must
keep shape (N,N,N), float32 dtype, and finite values. These tiny builds are
cheap and safe to run alongside the production build.
"""
import contextlib
import io
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


def _sample_inputs():
    df = build_grid.load_sample(SAMPLE)
    return build_grid.prepare_galaxies(df, 500.0)


def test_chunk_invariant():
    """Changing `chunk` must never change the grid output (byte-identical)."""
    xyz, mass = _sample_inputs()
    kw = dict(r_max=500.0, n=8, softening_mpc=0.5, exaggeration=1.0)

    a = build_grid.build_grid(xyz, mass, chunk=16, **kw)
    b = build_grid.build_grid(xyz, mass, chunk=512, **kw)
    auto = build_grid.build_grid(xyz, mass, chunk=0, **kw)  # AUTO
    default = build_grid.build_grid(xyz, mass, **kw)         # default chunk=0

    assert np.array_equal(a, b)
    assert np.array_equal(a, auto)
    assert np.array_equal(a, default)


def test_progress_output_byte_identical():
    """Production builds run with --progress; its output MUST match the
    default (progress-off) path byte-for-byte, else the shipped grid would
    differ from the committed one."""
    xyz, mass = _sample_inputs()
    kw = dict(r_max=500.0, n=8, softening_mpc=0.5, exaggeration=1.0)
    a = build_grid.build_grid(xyz, mass, progress=False, **kw)
    b = build_grid.build_grid(xyz, mass, progress=True, **kw)
    assert np.array_equal(a, b)


def test_progress_emitted():
    """progress=True writes to stderr; progress=False emits nothing."""
    xyz, mass = _sample_inputs()
    kw = dict(r_max=500.0, n=8, softening_mpc=0.5, exaggeration=1.0)

    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        build_grid.build_grid(xyz, mass, progress=True, **kw)
    text = buf.getvalue()
    assert text != ""
    assert "voxels" in text
    assert "%" in text

    buf2 = io.StringIO()
    with contextlib.redirect_stderr(buf2):
        build_grid.build_grid(xyz, mass, progress=False, **kw)
    assert buf2.getvalue() == ""
