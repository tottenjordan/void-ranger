# Implementation Plans

Numbered, titled implementation plans for Void Ranger. Each plan is a
self-contained record: the goal, context, bite-sized tasks, and verification.
Completed plans are kept as historical records (not deleted) — their status
header reflects what shipped.

| # | Plan | Status |
|---|------|--------|
| [001](001-cosmic-web-option-c.md) | Cosmic Web (Option C) — reach beyond the solar neighborhood | ✅ **Phase 1 shipped** (PR #6); Phase 2 → see 003 |
| [002](002-cosmic-web-phase-2-glade-gcp.md) | Cosmic Web Phase 2 — GLADE+ big-data (high-level sketch) | 📐 **Expanded → [003](003-cosmic-web-phase-2-deep-field.md)** |
| [003](003-cosmic-web-phase-2-deep-field.md) | Cosmic Web Phase 2 — Deep Field (GLADE+ on GCP), task-by-task | 🚧 **Largely implemented** — Deep Field scale shipped (tiles + grid + O(voxels) search; see [deep-field.md](../deep-field.md)); GCP provisioning suite remaining |

## Conventions

- **Numbering:** `NNN-kebab-title.md`, allocated in order; numbers are never
  reused. New plans take the next free number.
- **Status header:** every plan starts with a one-line status (Planned /
  In progress / Shipped) and links to the PR(s) that delivered it.
- **Don't mutate shipped plans** to add new scope — write a new numbered plan and
  cross-link. (That's why Phase 2 became 002 rather than an edit to 001.)
- These are planning artifacts. The authoritative state of the app is the code,
  the [deep-dive docs](../README.md), and git history.
