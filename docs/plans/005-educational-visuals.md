# 005 — Educational Visual Aids (PaperBanana diagrams + real-physics plots)

**Status:** ✅ **Implemented** on branch `feat/educational-visuals`. Twelve
figures generated, curated into `docs/images/`, and embedded across the README
and deep-dive docs. Docs-only — no app code or physics touched; backend suite
unchanged, `vite build` clean. PR open.

> **For Claude:** REQUIRED SUB-SKILL: this plan was executed
> subagent-driven (each implementation task: implementer → review → fix loop).

## Goal

Give every concept and every scale a purpose-built visual. The docs were strong
on text, LaTeX, and ASCII diagrams but `docs/images/` held only dashboard
screenshots — no conceptual/architecture art. This plan fills that gap with a
cohesive set of **explainer diagrams** plus **quantitative plots fed by the real
backend physics**, embedded inline next to the prose they illustrate.

## Approach

- **Diagrams** (concept + architecture + per-scale) were generated with
  **PaperBanana** (`paperbanana batch`, gemini image model) from prose specs that
  share a locked style preamble: flat-vector "explainer" art on a dark navy
  (`#0a0e1a`) starfield, accent **cyan `#22d3ee`** (void / Cosmic Server) and
  **amber `#f59e0b`** (Earth & its gravity well).
- **Plots** were generated with `paperbanana plot`, which emits and runs real
  **matplotlib** code — so the charts are pixel-faithful to the data. The data
  comes from a new generator, `backend/scripts/figures/gen_plot_data.py`, that
  imports `app.services.physics` (no math reimplemented) and writes JSON for each
  plot. Exact figures are also stated in the captions so the quantitative claims
  stay precise.
- Generated images are scratch (git-ignored `outputs/`; plot-data JSON in the
  git-ignored `backend/scripts/figures/_data/`). Only the **curated, renamed,
  compressed PNGs in `docs/images/`** are committed (resized to 1500–1600 px,
  256-color quantized → ~4.2 MB total for all 12, down from ~33 MB raw).

## The figure set (12) and where each is embedded

**Concept explainers**
- `concept-two-clocks` → `docs/gravitational-field.md`
- `concept-tradeoff` → `docs/efficiency-model.md`
- `concept-offload-flow` → `docs/README.md`

**Architecture / data-flow**
- `arch-system` → `README.md`
- `arch-deepfield-pipeline` → `docs/deep-field.md`
- `arch-tile-grid-streaming` → `docs/deep-field.md`
- `arch-single-service-cloudrun` → `backend/scripts/glade/gcp/DEPLOY.md` (ties to [004](004-single-service-cloudrun.md))

**Per-scale comparison**
- `scales-overview` → `README.md` **and** `docs/scaling-the-universe.md`

**Quantitative plots — real backend data**
- `plot-netgain-vs-distance` → `docs/efficiency-model.md`
- `plot-breakeven-vs-distance` → `docs/efficiency-model.md`
- `plot-latency-vs-distance` → `docs/light-latency.md`
- `plot-clock-advantage-per-scale` → `docs/cosmic-web.md` **and** `docs/deep-field.md`

New ASCII diagrams are complemented, not replaced — existing ASCII blocks are
kept in place beside the new art.

## Tasks (as executed)

0. Git-ignore scratch (`outputs/`, `backend/scripts/figures/_data/`).
1. Smoke-test PaperBanana + lock the shared style on `concept-two-clocks`.
2. Generate the 7 concept/architecture/per-scale diagrams (`paperbanana batch`).
3. Add `gen_plot_data.py` emitting real-physics JSON for the 4 plots.
4. Generate the 4 plots (`paperbanana plot`, real matplotlib).
5. Curate + compress the 12 winners into `docs/images/`.
6. Embed each figure next to its prose (README + deep-dive docs + DEPLOY.md).
7. This plan record + index row.

## Verification

- `gen_plot_data.py` runs clean; deepest-void clock advantages land in the
  documented teaching bands: **solar 1.058, cosmic 1.146, deep-field 1.060**.
- Round-trip latency (years, log axis) spans ~10¹ (solar ≈ 2,000 yr) to ~10⁹
  (cosmic / deep-field) — consistent with `light_latency` = 2d/c.
- All 12 PNGs present in `docs/images/`; every embed's relative path resolves
  (`scales-overview` and `plot-clock-advantage-per-scale` appear in 2 files
  each, the other 10 once).
- Docs-only: backend `pytest` unaffected, `npx vite build` clean,
  `git status` shows no `outputs/` or `_data/` tracked.

## Key decisions (carry forward)

- **Plots use real matplotlib via PaperBanana** (faithful), not AI-painted
  charts. The exact physics values are also written into the captions.
- **PaperBanana driven via CLI** (`uvx --from paperbanana paperbanana …`) with a
  Developer-API `GOOGLE_API_KEY`, bypassing the MCP server (its env is cached at
  launch and needs a restart to change). Style preamble + specs live in the
  scratch `outputs/specs/` (not committed).
- Only curated PNGs are committed; regenerating is reproducible from
  `gen_plot_data.py` + the specs.
