# Finding the Best Server Placements (Void Finding)

How Void Ranger auto-locates good places to deploy a Cosmic Server: the
**deepest void** (lowest local gravity → fastest clock) and the **best spot for a
given task** (highest net gain). Implemented in
[`backend/app/services/physics.py`](../backend/app/services/physics.py)
(`find_deepest_void`, `find_best_spot`) and exposed at
`POST /api/physics/best-void` and `POST /api/physics/best-spot`.

## 1. What "low gravity" actually means

The potential at a point is the **sum of every star's pull**, not a function of
distance from Earth:

```
Φ(r) = Σᵢ  G · Mᵢ / √( |r − rᵢ|² + ε² )    (over all 8,920 catalog stars)
```

So a **low-gravity location is one that is far from *all* massive stars — an
empty pocket** — *not* simply far from Earth. A point 300 pc away that sits next
to a bright star has a **high** potential (a deep well); a point sitting in a gap
between stars has a **low** one. **Distance from Earth only affects latency**
(`2d/c`), never the local gravity — see [Light-Speed Latency](light-latency.md)
and the [Gravitational Field Model](gravitational-field.md).

The deepest void is therefore the point that **minimizes the full sum** above —
equivalently, the center of the largest empty region (the "largest empty sphere"
idea). It is *not* "as far from Earth as possible."

### Why we still bound the search by a distance

If you minimized `Φ` with no constraint, the answer would run off toward empty
intergalactic space (`Φ → 0`) — gravitationally ideal but with absurd latency. So
we cap the search by a **max distance from Earth** purely as a **latency budget**
(and to give the search a finite region), not because distance lowers gravity.

A proof-of-concept sweep within 300 pc illustrates the distinction. The winner sat
near the 300 pc edge **but 57 pc from its nearest star** — it won on *emptiness*,
not raw distance:

| Point | Φ (J/kg) | Clock advantage | Note |
|-------|----------|-----------------|------|
| Deepest void within 300 pc ≈ `(−274, −72, 96)` | 4.0×10⁵ | **1.058×** | 57 pc from nearest star |
| Earth's crowded neighborhood (near origin) | 1.2×10⁶ | 1.005× | densest sampled region |

Voids *tend* to lie farther out only because the catalog is **magnitude-limited**:
star density is highest near Earth and thins outward, so emptier pockets are more
common at distance. That's a statistical/catalog artifact, not a physical law —
the search makes no distance assumption; it just evaluates the full sum.

## 2. Methods (easiest → best)

1. **Bounded grid / random sweep** — sample many points inside the distance cap,
   evaluate `Φ` (vectorized over all stars), take the minimum. Cheap and robust;
   refine with a finer local grid around the winner.
2. **Largest-empty-sphere (KD-tree)** — find the point whose *nearest-star*
   distance is maximized (a Voronoi-vertex problem). A good geometric proxy for an
   interior void; the KD-tree makes nearest-star queries fast.
3. **Continuous optimization** — the softened `Φ` is smooth and differentiable, so
   gradient descent / `scipy.optimize.minimize` converges quickly. Use multi-start
   (seeded from the grid winners) and keep it constrained, or it walks to the
   boundary.
4. **Maximize net gain (the product-meaningful version)** — what you usually want
   is the best place to *deploy*, which trades the void's clock advantage against
   light latency:
   ```
   net_gain = task · (1 − f_earth / f_server) − 2d/c
   ```
   Same search machinery, different objective. This naturally picks a deep-but-not-
   too-far void and depends on the current task size.

## 3. What Void Ranger implements

A **bounded, deterministic grid sweep with two-level local refinement**, for two
objectives:

- **Find deepest void** — minimizes `Φ` (method 1). `find_deepest_void(max_distance_pc)`.
- **Best spot for this task** — maximizes `net_gain` (method 4).
  `find_best_spot(task_seconds, max_distance_pc)`.

Both reuse `load_star_arrays()` and the existing potential/dilation/latency code,
evaluate candidates in memory-chunked NumPy, and return `{x, y, z}` — which the UI
feeds into the normal placement flow (metrics + camera fly-to). The search is
deterministic (a fixed grid, no RNG), so the same inputs always give the same spot.

Try them:

```bash
curl -s -X POST http://localhost:8000/api/physics/best-void \
  -H 'Content-Type: application/json' -d '{"max_distance_pc":300}'

curl -s -X POST http://localhost:8000/api/physics/best-spot \
  -H 'Content-Type: application/json' -d '{"task_seconds":3.6e12,"max_distance_pc":300}'
```

## 4. Caveats

- **Catalog / magnitude-limited.** Only the 8,920 bright HYG stars contribute, so
  "voids" are partly an artifact of missing faint stars and falling density with
  distance (see [Gravitational Field Model](gravitational-field.md#7-caveats--limitations)).
- **The bound is a latency budget, not physics.** Raising `max_distance_pc` finds
  emptier (lower-Φ) pockets but with larger latency; the "best spot" search trades
  these off, the "deepest void" search ignores latency by design.
- **Grid resolution.** The sweep is coarse-then-refined; it finds an excellent spot
  but not a provably global optimum. Good enough for placement guidance.
- **Exaggerated dilation.** Clock advantages use the deliberately-scaled gravity
  model — relative comparisons are faithful, absolute magnitudes are not.
