# Light-Speed Communication Latency

How Void Ranger computes the round-trip communication delay to a deep-space
server — the *Communication Cost* metric and the latency term in
[Earth Wait Time](efficiency-model.md). Implemented in
[`backend/app/services/physics.py`](../backend/app/services/physics.py)
(`light_latency`).

## 1. The formula

To use a server you must send the job out and receive the result back — two trips
at the speed of light. So the latency is the round-trip light-travel time:

```
latency = 2d / c,   d = √(x² + y² + z²)   (distance from Earth at the origin)
```

- `d` is the straight-line Earth↔server distance (parsecs, converted to km).
- `c` = 299,792.458 km/s.
- The factor of **2** is the round trip (dispatch + return).

That's the entire model — latency is pure light-travel time, nothing else. It's
what the UI shows as the **Communication Cost** card, and it's the term added to
compute time to get **Earth Wait Time**.

## 2. Latency depends only on distance

Unlike the clock rate (which depends on the *local gravity* around the server —
see the [Gravitational Field Model](gravitational-field.md)), latency depends
**only on how far the server is from Earth**. Two servers the same distance out
have identical latency even if one sits in a deep void and the other next to a
massive star. Distance is the single lever here; direction (galactic longitude /
latitude) doesn't matter, only the magnitude `d`.

## 3. Why latency is the thing that limits void-hunting

Latency grows **linearly** with distance (`2d/c`), while the time-dilation
advantage **saturates** (a void's clock can only get so much faster than Earth's).
So as you push the server farther out chasing a deeper void, the communication
tax climbs without bound while the per-second saving plateaus. That's exactly why
there's a [breakeven workload](efficiency-model.md#3-the-breakeven-workload):
beyond a certain distance, only an enormous job can amortize the round trip. It's
the same calculus as shipping a job to a distant data center — the network
round-trip is a fixed cost only worth paying if the job is big enough.

## 4. Worked example

Round-trip latency at a few distances (it scales linearly, so 10× the distance =
10× the delay):

| Distance from Earth | `latency = 2d/c` | In days | In years |
|---------------------|------------------|---------|----------|
| 1 pc | 2.06×10⁸ s | 2,383 days | 6.5 yrs |
| 10 pc | 2.06×10⁹ s | 23,828 days | 65.3 yrs |
| 100 pc | 2.06×10¹⁰ s | 238,282 days | 652.8 yrs |
| 400 pc | 8.24×10¹⁰ s | 953,128 days | 2,611.3 yrs |

Sanity check: 1 pc ≈ 3.26 light-years, so a *one-way* trip is ~3.26 years and the
round trip is ~6.52 years — matching the table. At 400 pc the round trip alone is
already **2,611 years**, which is why the deep-void examples need jobs measured in
tens of thousands of years to come out ahead.

Reproduce it (latency is independent of the task size you pass):

```bash
curl -s -X POST http://localhost:8000/api/physics/efficiency \
  -H 'Content-Type: application/json' \
  -d '{"x":400,"y":0,"z":0,"task_seconds":31536000}'
# → latency_seconds ≈ 8.235e10
```

## 5. Caveats

- **Pure light-travel time.** No relativistic Doppler, no router/processing
  overhead, no signal-attenuation limits — just `2d/c`.
- **Earth is the origin.** Distance is measured from `(0, 0, 0)`; the model has a
  single fixed endpoint (Earth) and one server.
- **No relativity in the latency itself.** The light delay is plain special-
  relativity kinematics (finite `c`); the *gravitational* time dilation is a
  separate effect handled by the [clock model](gravitational-field.md). They're
  combined only in [Earth Wait Time](efficiency-model.md).

## 6. Code map

| Piece | Location |
|-------|----------|
| `latency = 2d/c` | `light_latency` — `backend/app/services/physics.py` |
| Added into Earth Wait Time | `compute_efficiency` (see [Efficiency Model](efficiency-model.md)) |
| API wiring | `efficiency()` in `backend/app/routers/physics.py` |
