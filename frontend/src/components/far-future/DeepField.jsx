import { useRef, useMemo, useEffect, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { PointMaterial, Html } from '@react-three/drei'
import * as THREE from 'three'

// Total in-memory point budget across all active nodes. When the chosen LOD set
// exceeds this, the inline point-cap loop in the LOD walk (sort by depth/dist,
// then accumulate until full) drops the lowest-priority nodes rather than
// silently truncating the buffer.
const MAX_POINTS = 300_000

// Screen-size refinement threshold. A node refines into its children when it's
// visible AND its apparent angular size (worldDiameter / distanceToCenter)
// exceeds this. Larger value = must be closer/bigger to refine (coarser LOD);
// smaller = refines more eagerly. The sample tileset is tiny so the exact value
// isn't critical — this produces: root visible on entry, children stream in as
// you zoom toward a region.
const REFINE_SCREEN_SIZE = 0.6

// Hysteresis lower bound: a node that is ALREADY refined stays refined until its
// screen size drops below this (80% of the refine threshold). Without a deadband
// a node whose size hovers at the boundary would flap refine↔coarsen every LOD
// tick, rebuilding the full Float32Array + re-uploading GPU geometry each flip.
const COARSEN_SCREEN_SIZE = REFINE_SCREEN_SIZE * 0.8

// Above this active-point count, disable the per-pointermove raycast (which
// tests every point in the buffer) so hover doesn't stutter on dense buffers.
// Small/sample buffers keep hover.
const HOVER_RAYCAST_MAX = 60_000

// R3F/three.js disables per-object picking when `raycast` is a no-op FUNCTION.
// Passing `null` instead leaves `object.raycast === null`, so the raycaster calls
// `null(...)` on every pointermove → "object.raycast is not a function" once a
// dense tile set pushes the active point count past HOVER_RAYCAST_MAX (never hit
// by the tiny sample, but real with the full catalog). A no-op keeps hover off
// cheaply without throwing.
const NO_RAYCAST = () => null

// LOD recompute cadence — frustum/zoom walks at ~4 Hz, not every frame (mirrors
// StarLabels' 0.25s throttle).
const LOD_INTERVAL_S = 0.25

// Decode a tile arrayBuffer into an interleaved x,y,z Float32Array. Browsers are
// little-endian and the tiles are headerless LE Float32, so this is a direct view.
function decodeTile(buf) {
  return new Float32Array(buf)
}

export default function DeepField({ assetBase, unit = 'Mpc' }) {
  const spinRef = useRef()
  const { camera } = useThree()

  // --- streaming state (refs survive re-renders; never trigger re-render) ---
  const mounted = useRef(true)
  const manifest = useRef(null)          // parsed manifest.json
  // Unbounded by design for the current ~10-tile sample; a large production
  // tileset would need an LRU bound (with eviction logging) on this cache.
  const tileCache = useRef(new Map())    // node id -> Float32Array (decoded)
  const inFlight = useRef(new Map())     // node id -> Promise (de-dupe)
  const abortRef = useRef(null)          // AbortController for in-flight fetches

  // Active node set drives the rendered buffer. We bump a version counter only
  // when the active set actually changes, so the buffer useMemo reconciles
  // cleanly and we never rebuild on an unchanged frame.
  const [activeIds, setActiveIds] = useState([])
  const activeIdsRef = useRef([]) // mirror of activeIds for stale-free fetch callbacks
  const activeVersion = useRef(0)
  const lastKey = useRef('')

  const [hover, setHover] = useState(null) // { x, y, z, dist }

  // Keep the ref mirror of activeIds current for stale-free fetch callbacks.
  activeIdsRef.current = activeIds

  // Reused temporaries for the per-LOD-tick frustum walk (no per-frame allocs).
  const frustum = useRef(new THREE.Frustum())
  const projScreenMatrix = useRef(new THREE.Matrix4())
  const centerTmp = useRef(new THREE.Vector3())
  const camTmp = useRef(new THREE.Vector3())
  const sphereTmp = useRef(new THREE.Sphere())
  const elapsed = useRef(0)

  // ---- fetch a tile (de-duped, cached, abortable) ----
  const ensureTile = useRef(null)
  ensureTile.current = (id) => {
    const m = manifest.current
    if (!m) return
    if (tileCache.current.has(id)) return
    if (inFlight.current.has(id)) return
    const node = m.nodes[id]
    if (!node || !node.file) return
    const url = `${assetBase}/tiles/${node.file}`
    const p = fetch(url, { signal: abortRef.current?.signal })
      .then(res => {
        if (!res.ok) throw new Error(`tile ${id} HTTP ${res.status}`)
        return res.arrayBuffer()
      })
      .then(buf => {
        if (!mounted.current) return
        tileCache.current.set(id, decodeTile(buf))
        inFlight.current.delete(id)
        // A newly-arrived tile may belong to the current active set; force a
        // rebuild so it shows up without waiting for the set to change.
        if (activeIdsRef.current.includes(id)) {
          activeVersion.current += 1
          setActiveIds(prev => [...prev]) // new array ref -> rebuild
        }
      })
      .catch(err => {
        inFlight.current.delete(id)
        if (err.name !== 'AbortError') {
          console.warn(`[DeepField] failed to load tile ${id}:`, err.message)
        }
      })
    inFlight.current.set(id, p)
  }

  // ---- load manifest on mount / assetBase change ----
  useEffect(() => {
    if (!assetBase) return
    mounted.current = true
    abortRef.current = new AbortController()
    const ac = abortRef.current

    fetch(`${assetBase}/tiles/manifest.json`, { signal: ac.signal })
      .then(res => {
        if (!res.ok) throw new Error(`manifest HTTP ${res.status}`)
        return res.json()
      })
      .then(json => {
        if (!mounted.current) return
        manifest.current = json
        // Load the root immediately for a coarse cloud on entry.
        const root = json.root
        if (root) {
          ensureTile.current(root)
          activeVersion.current += 1
          lastKey.current = root
          setActiveIds([root])
        }
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          console.warn('[DeepField] failed to load manifest:', err.message)
        }
      })

    return () => {
      mounted.current = false
      ac.abort()
      manifest.current = null
      tileCache.current.clear()
      inFlight.current.clear()
      lastKey.current = ''
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assetBase])

  // ---- spin + throttled LOD walk ----
  useFrame((_, delta) => {
    if (spinRef.current) spinRef.current.rotation.y += delta * 0.005

    const m = manifest.current
    if (!m || !spinRef.current) return

    elapsed.current += delta
    if (elapsed.current < LOD_INTERVAL_S) return
    elapsed.current = 0

    projScreenMatrix.current.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse)
    frustum.current.setFromProjectionMatrix(projScreenMatrix.current)
    const matrixWorld = spinRef.current.matrixWorld
    camera.getWorldPosition(camTmp.current)

    // Walk the octree, collecting the active (renderable) node set.
    const active = [] // { id, depth, dist }
    const visit = (id, depth) => {
      const node = m.nodes[id]
      if (!node) return
      const [minx, miny, minz, maxx, maxy, maxz] = node.bounds
      // Bounding sphere: center = midpoint, radius = half the diagonal. A
      // sphere radius is rotation-invariant, so transforming just the center by
      // the spinning group's matrixWorld is a correct world-space cull.
      centerTmp.current.set((minx + maxx) / 2, (miny + maxy) / 2, (minz + maxz) / 2)
      centerTmp.current.applyMatrix4(matrixWorld)
      const radius = 0.5 * Math.hypot(maxx - minx, maxy - miny, maxz - minz)

      sphereTmp.current.center.copy(centerTmp.current)
      sphereTmp.current.radius = radius
      if (!frustum.current.intersectsSphere(sphereTmp.current)) {
        return // off-screen subtree pruned
      }

      const dist = Math.max(centerTmp.current.distanceTo(camTmp.current), 1e-3)
      const screenSize = (2 * radius) / dist // worldDiameter / distance proxy
      const children = node.children || []
      // Hysteresis: if this node is already refined (its children were active
      // last pass), keep refining until size drops below the lower bound; only
      // an un-refined node must clear the higher REFINE bound to refine. This
      // deadband stops boundary flapping that would rebuild the buffer each tick.
      const currentlyRefined = children.length > 0 && children.some(c => activeIdsRef.current.includes(c))
      const refine = currentlyRefined
        ? screenSize > COARSEN_SCREEN_SIZE
        : screenSize > REFINE_SCREEN_SIZE

      if (refine && children.length > 0) {
        for (const c of children) visit(c, depth + 1)
      } else {
        active.push({ id, depth, dist })
        ensureTile.current(id)
      }
    }
    visit(m.root, 0)

    // Always keep the root as a fallback so something is shown even if every
    // refined leaf is mid-fetch.
    if (active.length === 0) {
      active.push({ id: m.root, depth: 0, dist: 0 })
      ensureTile.current(m.root)
    }

    // Enforce the point cap: prefer coarser (lower depth) and nearer nodes;
    // drop the deepest/farthest first. Count only points already decoded.
    active.sort((a, b) => (a.depth - b.depth) || (a.dist - b.dist))
    const kept = []
    let total = 0
    let dropped = 0
    for (const n of active) {
      const arr = tileCache.current.get(n.id)
      const pts = arr ? arr.length / 3 : 0
      if (total + pts > MAX_POINTS && kept.length > 0) {
        dropped += 1
        continue
      }
      total += pts
      kept.push(n.id)
    }
    if (dropped > 0) {
      console.warn(`[DeepField] point cap ${MAX_POINTS} reached — dropped ${dropped} node(s) this LOD pass`)
    }

    kept.sort()
    const key = kept.join(',')
    if (key !== lastKey.current) {
      lastKey.current = key
      activeVersion.current += 1
      setActiveIds(kept)
    }
  })

  // ---- build the merged position buffer from active decoded tiles ----
  const positions = useMemo(() => {
    let total = 0
    for (const id of activeIds) {
      const arr = tileCache.current.get(id)
      if (arr) total += arr.length
    }
    const out = new Float32Array(total)
    let off = 0
    for (const id of activeIds) {
      const arr = tileCache.current.get(id)
      if (arr) {
        out.set(arr, off)
        off += arr.length
      }
    }
    return out
    // activeVersion bumps whenever the set OR a newly-decoded tile changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeIds])

  const count = positions.length / 3

  const handlePointerMove = (e) => {
    e.stopPropagation()
    if (e.index == null) return
    const i = e.index * 3
    const x = positions[i], y = positions[i + 1], z = positions[i + 2]
    if (x == null) return
    setHover({ x, y, z, dist: Math.sqrt(x * x + y * y + z * z) })
  }
  const handlePointerOut = () => setHover(null)

  return (
    <group ref={spinRef}>
      {count > 0 && (
        <points
          onPointerMove={handlePointerMove}
          onPointerOut={handlePointerOut}
          raycast={count > HOVER_RAYCAST_MAX ? NO_RAYCAST : undefined}
        >
          {/* key on the active-set version so R3F disposes the old geometry on rebuild */}
          <bufferGeometry key={activeVersion.current}>
            <bufferAttribute attach="attributes-position" array={positions} count={count} itemSize={3} />
          </bufferGeometry>
          <PointMaterial
            size={1.0}
            sizeAttenuation
            color="#bcd4ff"
            transparent
            opacity={0.8}
            depthWrite={false}
          />
        </points>
      )}
      {hover && (
        <Html
          position={[hover.x, hover.y, hover.z]}
          style={{ pointerEvents: 'none', transform: 'translate(-50%, -115%)' }}
        >
          <span className="text-[10px] font-mono text-gray-200/90 bg-gray-950/70 px-1.5 py-0.5 rounded whitespace-nowrap">
            {hover.dist.toFixed(1)} {unit}
          </span>
        </Html>
      )}
    </group>
  )
}
