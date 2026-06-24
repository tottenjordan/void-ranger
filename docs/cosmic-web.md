# The Cosmic Web scale

Void Ranger has three **scales**, switched by the toggle in the top bar:

- **Solar Neighborhood** — ~8,920 stars within ~560 pc (the default; see the
  [Gravitational Field Model](gravitational-field.md)).
- **Cosmic Web** — ~43,500 galaxies out to a few hundred **megaparsecs**, where
  "place a compute node in a void" plays out among real galaxies and cosmic
  voids. *(This doc.)*
- **Deep Field** — **GLADE+** (~22.5 M galaxies), megaparsecs: the same cosmic
  premise as a big-data visualization, streamed as binary LOD tiles with a
  precomputed potential grid (O(voxels) void search). See
  [The Deep Field scale](deep-field.md).

Same premise at every scale: weaker local gravity → a faster clock → a job
finishes in less home time, traded off against light-speed latency. The cosmic
scale just zooms out by a factor of ~a million (parsecs → megaparsecs); the Deep
Field keeps these megaparsec units and scales the *catalog* up by ~500×.

## The catalog (2MRS)

The galaxies come from the **2MASS Redshift Survey** (Huchra+ 2012, VizieR
`J/ApJS/199/26`), built by `backend/scripts/process_galaxies.py` into
`backend/data/galaxies.json`:

- **~43,510 galaxies** with a usable redshift; median distance ~120 Mpc,
  reaching ~740 Mpc.
- **Distance** = Hubble distance `d = cz / H0` with `H0 = 70 km/s/Mpc`; Cartesian
  position in **Mpc** (same RA/Dec → x,y,z convention as the stars).
- **Mass** is a crude **K-band stellar-mass proxy**: `M ≈ 0.8 · L_K` (from the
  apparent K magnitude + distance), clamped to `1e8–5e12 M☉`. K-band light
  traces stellar mass reasonably well, but this ignores dark matter, gas, and
  galaxy type — good enough for *relative* potential, not precision cosmology.
- **18 famous galaxies** (Andromeda, Triangulum, M81/82, Centaurus A, Sombrero,
  Virgo A, …) are anchored at their **literature distances** and given proper
  names. Their redshift distance is unreliable (they're so nearby that peculiar
  velocities dominate, and some are blueshifted), so the curated table overrides
  it — the cosmic-scale parallel to stellar proper names. These are the labels
  you see; hovering any other galaxy shows its 2MASX designation, distance, and
  magnitude.

## The physics (why scale makes the premise *more* honest)

At star scale the time-dilation effect is real but minuscule (~1 part in 10¹³),
so it's deliberately **exaggerated** to be visible. At galaxy/cluster scale the
thesis is **literally true and measured**: clocks in cosmic voids genuinely tick
faster than clocks deep in galaxy clusters (the gravitational redshift between
voids and clusters is a real effect). So the cosmic scale uses a **much smaller
exaggeration**.

The model is the same weak-field one, with the catalog and constants swapped per
scale (`SCALES` registry in `backend/app/services/physics.py`):

| Quantity | Solar | Cosmic |
|---|---|---|
| Length unit | parsec (`3.086e16 m`) | megaparsec (`3.086e22 m`) |
| Softening `ε` | 0.1 pc | 0.5 Mpc |
| Gravity exaggeration | `5.5e9` | `1.0e5` (≈55,000× smaller) |
| Catalog | `stars.json` | `galaxies.json` |

Everything else is identical: clock factor `f = √(1 + 2Φ/c²)` with the softened
potential `Φ = −Σ G·Mᵢ/√(r²+ε²)` summed over the catalog; Earth (our vantage
point) sits at the origin; `f_server/f_earth` is the **clock advantage**; latency
is `2d/c`; and `Earth Compute / Wait / Net Gain / Breakeven` follow the
[Efficiency & Breakeven](efficiency-model.md) math unchanged.

**Calibration.** The cosmic exaggeration (`1.0e5`) is tuned so the *deepest void*
within ~100 Mpc lands a clock advantage of ~**1.05** (a visible but modest few
percent). Pushing it much higher saturates the well-depth cap at both Earth and
the void, collapsing the advantage back toward 1.0 — so it sits deliberately in
the lower window.

**Latency dominates at these distances.** Round-trip light time is `2d/c`: ~327
**million** years at 50 Mpc, ~1.3 **billion** years at 200 Mpc. So the cosmic
scale vividly shows the core trade-off — only an astronomically large job, placed
in a *nearby* void, ever nets a gain; most placements are correctly a net loss
dominated by light delay. (The app's "years" display absorbs these huge numbers
naturally.)

## Find deepest void / Best spot (cosmic)

The same finders work at this scale, searching within a radius **in Mpc**: *Find
deepest void* minimizes the galaxy potential (the emptiest pocket — a real cosmic
void), and *Best spot for this task* maximizes net gain against the Mpc-scale
latency. See [Void Finding](void-finding.md).

## Caveats (cosmic-specific)

1. **Point-mass galaxies.** Each galaxy is a single softened point mass — no
   halo profile, no dark-matter distribution. Fine for the relative potential
   field; not a real N-body cosmology.
2. **Crude masses.** K-band `M/L ≈ 0.8` ignores dark matter, gas, and morphology.
   Relative comparisons between regions are meaningful; absolute masses are not.
3. **Hubble distance only.** `d = cz/H0` conflates peculiar velocity with
   distance (worst for nearby galaxies — hence the curated overrides) and treats
   light-travel ≈ comoving distance, valid only at low redshift (2MRS reaches
   z ≈ 0.03). No cosmological expansion is modeled in the latency.
4. **Still exaggerated.** Smaller than the stellar case, but the dilation
   magnitude is scaled for visibility — the *trade-off structure* is faithful,
   the absolute percentages are not.
5. **"Earth" = our vantage point.** At Mpc scale the origin marker labeled
   "Earth" really means the Milky Way / Local Group; we keep the "Earth" noun for
   consistency with the metric cards (Earth Compute/Wait Time).

## Code map

| Piece | Location |
|---|---|
| Catalog pipeline | `backend/scripts/process_galaxies.py` |
| Galaxy data | `backend/data/galaxies.json` |
| Scale registry + parameterized physics | `SCALES` in `backend/app/services/physics.py` |
| Catalog loaders | `load_galaxies`, `load_galaxy_arrays` — `backend/app/services/catalog.py` |
| API | `GET /api/galaxies`; `scale` field on `/api/physics/efficiency`, `/best-void`, `/best-spot` |
| Scale toggle + UI | `SCALE_UI` in `frontend/src/components/far-future/FarFutureView.jsx` |
