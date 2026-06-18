# Gravitational Field & Clock-Rate Model

How Void Ranger computes the gravitational potential — and therefore the clock
rate — at **any** coordinate you place a server, including coordinates that
happen to sit close to other stars. All of this lives in
[`backend/app/services/physics.py`](../backend/app/services/physics.py); this
doc is the deeper-dive companion to the README's
[Physics and Assumptions](../README.md#physics-and-assumptions) section.

## 1. The potential at a point

For any point `r = (x, y, z)` (in parsecs), the gravitational potential is the
**softened Newtonian sum over every one of the 8,920 catalog stars**:

```
Φ(r) = Σᵢ  G · Mᵢ / √( |r − rᵢ|² + ε² )
```

- `G` = 6.674×10⁻¹¹ m³·kg⁻¹·s⁻², `Mᵢ` = the i-th star's mass, `rᵢ` = its position.
- `ε` = **softening length = 0.1 pc** (`SOFTENING_M`).
- Implemented in `local_potential(x, y, z)` — a single NumPy vectorized sum over
  the whole star array, so **every star contributes** `G·M/r` to the potential
  at that point. It's O(N) per query (~8,920 terms), which is instant.

**This is the whole answer to "what if my coordinate is near another body":** it
is handled automatically by the sum. There is no special case. If your point is
near a star, that star's `1/r` term dominates the sum, the potential spikes, the
well deepens, and the server's clock slows down. If your point is in empty space,
only the small far-field tails of distant stars contribute and the potential is
low (a fast clock).

### Distance from Earth ≠ gravity

A key, easy-to-miss point: the **clock rate depends only on the local potential**
(the stars near *that* point) — **not** on how far the point is from Earth.
Distance from Earth only sets the communication **latency** (`light_latency`,
round-trip `2d/c`). So two servers the same distance out can behave completely
differently: one in a void runs fast, one parked next to a bright star runs slow.
(See the worked example in §6.)

## 2. Proximity to a star, and the softening length

Because the potential is a literal sum of `G·M/r` terms, getting close to a star
raises the potential sharply. Two consequences:

- **Near a star → slower clock.** The closer you are, the larger that star's
  contribution, the deeper the well, the lower the server's clock factor.
- **Right on top of a star stays finite.** A pure `1/r` would blow up to infinity
  at `r = 0`. The `ε² = (0.1 pc)²` term inside the square root caps a single
  star's contribution at `G·M/ε` instead of `∞`, so a near-direct hit produces a
  **deep but bounded** well — never a singularity, never a crash.

In short: a "void" in this app means **far from bright catalog stars**, and the
penalty for placing a server near mass falls straight out of the physics.

## 3. From potential to clock rate

The potential is converted to a clock-rate factor with the weak-field relation
(`gravitational_dilation`):

```
f = √( 1 − depth ),   depth = min( k · 2Φ/c² , 0.7 )
```

- `f` is `dτ/dt` — how fast a clock there ticks relative to flat spacetime.
  `f → 1` in a perfect void; smaller `f` = deeper in a gravity well = slower clock.
- `k` = `GRAVITY_EXAGGERATION` = **5.5×10⁹** (see §5 — real interstellar dilation
  is invisible without it).
- `depth` is capped at `MAX_WELL_DEPTH = 0.7` so `f` stays real and sane even in
  the deepest wells.

Earth's own factor `f_earth` is this exact same calculation evaluated at the
origin `(0,0,0)` — deep in the dense solar neighborhood — and is cached
(`earth_dilation_factor`). The number the UI shows as **Server Clock Advantage**
is simply:

```
clock_advantage = f_server / f_earth
```

`> 1` (cyan) → the server's clock runs faster than Earth's (a void advantage);
`< 1` (red) → it's in a region *denser* than Earth's neighborhood, so it runs
slower; offloading there can never win (its breakeven is reported as "none").

## 4. Why Earth is a high bar

Earth's potential is the sum at the origin over **all** nearby stars (the nearest
is 1.3 pc away), so `f_earth ≈ 0.921`. That summed neighborhood is a surprisingly
high bar: a *single* distant star, even placed right at the softening distance,
contributes at most `G·M/ε`. For a typical massive catalog star (~10–15 M☉) that
ceiling is **below** Earth's summed potential — which is why placing a server on
a moderate star still leaves the advantage slightly above 1. You only flip below
1× when the local potential actually exceeds Earth's — i.e., next to a genuinely
massive star (≳16 M☉ at a few hundred pc) or inside a dense clump.

## 5. Where the masses come from

Each star's `Mᵢ` is **estimated from its catalog luminosity** using the
main-sequence mass–luminosity relation, clamped to a sane range:

```
M / M☉ = (L / L☉)^(1/3.5),   clamped to 0.1 – 50 M☉
```

(done once in the data pipeline, `backend/scripts/process_stars.py`). This is a
crude estimate — it treats every star as main-sequence, ignoring giants, white
dwarfs, and binaries — but it's enough to make the *relative* geography of voids
vs. crowded regions meaningful.

## 6. Worked example: a void vs. next to a massive star

Same distance from Earth (so the **latency is identical**), but very different
gravity. Using a real catalog star — a **22 M☉ star at 264.6 pc**,
`(x, y, z) = (51.6, 256.7, −37.7)` — versus an empty point the same distance out:

| Placement (both at 264.6 pc) | `f_server` | Server Clock Advantage | Breakeven workload |
|------------------------------|-----------|------------------------|--------------------|
| Deep void `(0, 0, 264.6)`    | 0.9708    | **1.0535×** (green, +5.35%) | ≈ 34,000 years |
| **On the 22 M☉ star**        | 0.9063    | **0.9835×** (red, −1.65%)   | **none** |

`f_earth = 0.9215` in both cases. The void runs 5.35% faster than Earth, so a big
enough job nets a gain (breakeven ≈ 34,000 yr). Move to the same distance but on
top of the massive star and the local potential now *exceeds* Earth's — the clock
runs **slower** than Earth's, so offloading is a net loss at *any* task size, and
the breakeven readout shows "none."

A milder case shows the gradient: on an **11 M☉ star at 211 pc** the advantage
drops from **1.0476×** (void) to **1.0145×** (on the star) — penalized, but still
above 1, because a single 11 M☉ star can't outweigh Earth's whole neighborhood.

You can reproduce these by deploying a server at those coordinates in the app, or
directly:

```bash
curl -s -X POST http://localhost:8000/api/physics/efficiency \
  -H 'Content-Type: application/json' \
  -d '{"x":51.601,"y":256.710,"z":-37.740,"task_seconds":3153600000000}'
```

## 7. Caveats & limitations

- **Catalog-only.** Only the 8,920 HYG stars brighter than magnitude 6.5
  contribute. Interstellar gas, dark matter, the galaxy's smooth mass field, and
  fainter unlisted stars are all ignored — so "void" really means "far from
  bright catalog stars."
- **Magnitude-limited → density falls with distance.** Because the catalog only
  includes bright stars, star density drops off away from Earth, which makes
  distant regions read as low-potential voids partly as a *catalog artifact*, not
  pure physics.
- **Deliberately exaggerated.** Real interstellar dilation is ~1 part in 10¹³ —
  utterly invisible. `GRAVITY_EXAGGERATION` scales it into a visible
  few-to-tens-of-percent effect. **Relative** differences between placements are
  faithful; the **absolute** magnitudes are not physical.
- **Newtonian weak-field.** We use `f = √(1 + 2Φ/c²)`, valid only for weak fields
  — there are no black-hole / strong-field effects here.
- **Coordinate-frame mismatch.** Catalog stars are placed from equatorial
  (RA/Dec) coordinates while the server form uses galactic longitude/latitude.
  The potential is computed in the same Cartesian frame the stars are stored in,
  so it is internally **self-consistent**, but a server's coordinates don't
  correspond to the *true* galactic-frame position relative to those stars.

## 8. Code map

| Piece | Location |
|-------|----------|
| Potential `Φ(r)` (the sum) | `local_potential` — `backend/app/services/physics.py` |
| Clock factor `f = √(1 − depth)` | `gravitational_dilation` — same file |
| Earth's factor (cached, at origin) | `earth_dilation_factor` |
| Server's factor (at x,y,z) | `server_dilation_factor` |
| Constants (`G`, `ε`, exaggeration, cap) | top of `physics.py` |
| Star positions + estimated masses | `backend/app/services/catalog.py`, built by `backend/scripts/process_stars.py` |
