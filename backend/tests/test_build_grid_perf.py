"""Pinning + structural tests for the Deep Field grid builder (scripts/glade/build_grid.py).

Pins current build_grid behavior at small N (N=8 on the committed ~20k-row
sample) so the Phase C optimization refactors stay byte-faithful: the grid must
keep shape (N,N,N), float32 dtype, and finite values. These tiny builds are
cheap and safe to run alongside the production build.
"""
import contextlib
import io
import os
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


def test_parallel_matches_serial():
    """The parallel (jobs>1) path must be byte-identical to the serial one.

    Parallelism splits WHICH voxels each worker computes; each voxel still
    reduces over the same galaxy array in the same order, so the reassembled
    grid must equal the serial result exactly (no ULP drift).
    """
    xyz, mass = _sample_inputs()
    kw = dict(r_max=500.0, n=16, softening_mpc=0.5, exaggeration=1.0)
    a = build_grid.build_grid(xyz, mass, jobs=1, **kw)
    b = build_grid.build_grid(xyz, mass, jobs=4, **kw)
    assert np.array_equal(a, b)


def test_parallel_progress_streams_multiple_updates():
    """Parallel --progress must emit MANY updates (not just one per worker), so a
    long build shows a live ETA. With jobs=2 the build is split into
    2 * RANGES_PER_JOB ranges, so we expect well more than 2 progress lines."""
    xyz, mass = _sample_inputs()
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        grid = build_grid.build_grid(
            xyz, mass, r_max=500.0, n=8, softening_mpc=0.5,
            exaggeration=1.0, jobs=2, progress=True,
        )
    lines = [ln for ln in buf.getvalue().splitlines() if "[build_grid]" in ln]
    assert len(lines) > 2  # more than `jobs` updates → progress streams throughout
    # And it must still be byte-identical to the serial build.
    serial = build_grid.build_grid(
        xyz, mass, r_max=500.0, n=8, softening_mpc=0.5,
        exaggeration=1.0, jobs=1, progress=False,
    )
    assert np.array_equal(grid, serial)


def test_matches_committed_sample_grid():
    """Regression gate: the optimized builder must reproduce the shipped grid.

    Rebuilds the grid from the committed sample inputs at the exact resolution
    and parameters used to produce the committed grid.npy, then asserts strict
    byte-identity. This justifies that no GCS re-upload is needed after the
    Phase C optimization.
    """
    xyz, mass = _sample_inputs()
    rebuilt = build_grid.build_grid(
        xyz,
        mass,
        r_max=500.0,
        n=48,
        softening_mpc=0.5,
        exaggeration=1.0,
        jobs=os.cpu_count() or 1,
    )
    committed = np.load(
        BACKEND_DIR / "data" / "samples" / "deepfield" / "grid" / "grid.npy"
    )
    assert rebuilt.shape == committed.shape
    assert np.array_equal(rebuilt, committed)
