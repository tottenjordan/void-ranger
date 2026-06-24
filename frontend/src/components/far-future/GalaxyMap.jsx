import { useRef, useMemo, useEffect, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Stars, PointMaterial, Float, Sparkles, Grid, Html, Line } from '@react-three/drei'
import * as THREE from 'three'
import { humanDuration } from '../../utils/format'
import { SHARED_SCENE } from './FarFutureView'
import DeepField from './DeepField'

const PARSEC_KM = 3.086e13
const C_KM_S = 299792.458

// How many bright named stars to persistently label at once.
const MAX_LABELS = 8

// Persistent labels for the brightest named stars currently inside the camera
// frustum. Rendered as a child of StarField's rotating group, so the labels
// share the group's transform and track the points without per-frame syncing.
function StarLabels({ stars, spinRef }) {
  const { camera } = useThree()
  const [shownIndices, setShownIndices] = useState([])

  // Precompute the named subset once (local positions + magnitude).
  const named = useMemo(
    () =>
      stars
        .map((s, i) => ({ i, s }))
        .filter(({ s }) => s.name)
        .map(({ i, s }) => ({ i, s, pos: new THREE.Vector3(s.x, s.y, s.z), mag: s.mag })),
    [stars],
  )

  // Reused temporaries — avoid per-frame allocations in the hot path.
  const frustum = useRef(new THREE.Frustum())
  const projScreenMatrix = useRef(new THREE.Matrix4())
  const worldTmp = useRef(new THREE.Vector3())
  const elapsed = useRef(0)
  const lastKey = useRef('')

  useFrame((_, delta) => {
    if (!spinRef.current) return
    // Throttle to ~4 Hz; frustum culling every frame is wasteful.
    elapsed.current += delta
    if (elapsed.current < 0.25) return
    elapsed.current = 0

    projScreenMatrix.current.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse)
    frustum.current.setFromProjectionMatrix(projScreenMatrix.current)

    const matrixWorld = spinRef.current.matrixWorld
    const picked = []
    for (const entry of named) {
      worldTmp.current.copy(entry.pos).applyMatrix4(matrixWorld)
      if (frustum.current.containsPoint(worldTmp.current)) picked.push(entry)
    }
    picked.sort((a, b) => a.mag - b.mag) // brightest (lowest mag) first
    const top = picked.slice(0, MAX_LABELS)

    // Only setState when the chosen set actually changed.
    const key = top.map(p => p.i).join(',')
    if (key !== lastKey.current) {
      lastKey.current = key
      setShownIndices(top.map(p => p.i))
    }
  })

  return (
    <>
      {shownIndices.map(i => {
        const s = stars[i]
        return (
          <Html
            key={i}
            position={[s.x, s.y, s.z]}
            style={{ pointerEvents: 'none', transform: 'translate(-50%, -140%)' }}
          >
            <span className="text-[10px] font-mono text-gray-200/90 bg-gray-950/70 px-1 py-0.5 rounded whitespace-nowrap">
              {s.name}
            </span>
          </Html>
        )
      })}
    </>
  )
}

function StarField({ stars, unit }) {
  const spinRef = useRef()
  const [hoveredIndex, setHoveredIndex] = useState(null)

  const { positions, colors } = useMemo(() => {
    const positions = new Float32Array(stars.length * 3)
    const colors = new Float32Array(stars.length * 3)
    const color = new THREE.Color()

    stars.forEach((s, i) => {
      positions[i * 3] = s.x
      positions[i * 3 + 1] = s.y
      positions[i * 3 + 2] = s.z

      const warmth = Math.min(s.size / 3, 1)
      color.setHSL(0.6 - warmth * 0.15, 0.3 + warmth * 0.4, 0.7 + warmth * 0.2)
      colors[i * 3] = color.r
      colors[i * 3 + 1] = color.g
      colors[i * 3 + 2] = color.b
    })
    return { positions, colors }
  }, [stars])

  useFrame((_, delta) => {
    if (spinRef.current) spinRef.current.rotation.y += delta * 0.005
  })

  const handlePointerMove = (e) => {
    e.stopPropagation()
    if (e.index != null) setHoveredIndex(e.index)
  }

  const handlePointerOut = () => setHoveredIndex(null)

  const hovered = hoveredIndex != null ? stars[hoveredIndex] : null
  const hoveredDistance = hovered
    ? Math.sqrt(hovered.x ** 2 + hovered.y ** 2 + hovered.z ** 2)
    : 0

  return (
    <group ref={spinRef}>
      <points onPointerMove={handlePointerMove} onPointerOut={handlePointerOut}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" array={positions} count={stars.length} itemSize={3} />
          <bufferAttribute attach="attributes-color" array={colors} count={stars.length} itemSize={3} />
        </bufferGeometry>
        <PointMaterial
          size={1.2}
          sizeAttenuation
          vertexColors
          transparent
          opacity={0.85}
          depthWrite={false}
        />
      </points>
      <StarLabels stars={stars} spinRef={spinRef} />
      {hovered && (
        <Html
          position={[hovered.x, hovered.y, hovered.z]}
          style={{ pointerEvents: 'none', transform: 'translate(-50%, -115%)' }}
        >
          <div className="flex flex-col items-center whitespace-nowrap">
            <span className="text-sm font-bold font-mono text-gray-100 bg-gray-950/80 px-2 py-0.5 rounded">
              {hovered.name || hovered.desig}
            </span>
            <span className="text-[10px] font-mono text-gray-400 bg-gray-950/70 px-1.5 py-0.5 rounded mt-0.5">
              {hovered.con ? `${hovered.con} · ` : ''}{hoveredDistance.toFixed(1)} {unit} · mag {hovered.mag}
            </span>
          </div>
        </Html>
      )}
    </group>
  )
}

function EarthMarker({ originLabel }) {
  return (
    <group position={[0, 0, 0]}>
      <mesh>
        <sphereGeometry args={[1.5, 16, 16]} />
        <meshStandardMaterial color="#22c55e" emissive="#22c55e" emissiveIntensity={0.3} />
      </mesh>
      {/* Anchor the label's bottom just above the sphere (screen-space transform,
          so it stays clear of the object at any zoom). */}
      <Html position={[0, 2, 0]} style={{ pointerEvents: 'none', transform: 'translate(-50%, -120%)' }}>
        <span className="text-sm font-bold font-mono text-green-400 bg-gray-950/80 px-2 py-0.5 rounded whitespace-nowrap">
          {originLabel}
        </span>
      </Html>
    </group>
  )
}

function CommLine({ serverPosition }) {
  const pulseRef = useRef()

  const points = useMemo(() => [
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(serverPosition?.x ?? 0, serverPosition?.y ?? 0, serverPosition?.z ?? 0),
  ], [serverPosition])

  useFrame(({ clock }) => {
    if (!pulseRef.current) return
    const t = (clock.getElapsedTime() % 4) / 4
    const ping = t < 0.5 ? t * 2 : 2 - t * 2
    pulseRef.current.position.lerpVectors(points[0], points[1], ping)
  })

  if (!serverPosition) return null

  const distPc = Math.sqrt(serverPosition.x ** 2 + serverPosition.y ** 2 + serverPosition.z ** 2)
  const roundTripSeconds = (2 * distPc * PARSEC_KM) / C_KM_S

  return (
    <group>
      <Line
        points={points}
        color="#ef4444"
        lineWidth={2}
        dashed
        dashSize={3}
        gapSize={2}
        opacity={0.6}
        transparent
      />
      <group ref={pulseRef}>
        <mesh>
          <sphereGeometry args={[1.1, 12, 12]} />
          <meshBasicMaterial color="#ef4444" />
        </mesh>
        <mesh>
          <sphereGeometry args={[2.4, 12, 12]} />
          <meshBasicMaterial color="#ef4444" transparent opacity={0.25} depthWrite={false} />
        </mesh>
      </group>
      <Html
        position={[serverPosition.x, serverPosition.y + 3, serverPosition.z]}
        style={{ pointerEvents: 'none', transform: 'translate(-50%, -115%)' }}
      >
        <div className="flex flex-col items-center whitespace-nowrap">
          <span className="text-sm font-bold font-mono text-cyan-300 bg-gray-950/80 px-2 py-0.5 rounded">
            Cosmic Server
          </span>
          <span className="text-[10px] font-mono text-cyan-400 bg-gray-950/70 px-1.5 py-0.5 rounded mt-0.5">
            RTT {humanDuration(roundTripSeconds, 1)}
          </span>
        </div>
      </Html>
    </group>
  )
}

// A dimension line (architectural style) showing the straight-line Earth↔server
// distance. Drawn parallel to and offset above the comm line so the two never
// overlap, with the distance label at its midpoint.
function DistanceLine({ serverPosition, unit }) {
  const { points, mid, offset } = useMemo(() => {
    const sx = serverPosition?.x ?? 0
    const sy = serverPosition?.y ?? 0
    const sz = serverPosition?.z ?? 0
    const dist = Math.sqrt(sx * sx + sy * sy + sz * sz)
    // Vertical offset scales with distance (18%, min 4 units) so the dimension
    // line stays clear of the comm line; farther servers push it higher.
    const off = Math.max(dist * 0.18, 4)
    const p = [new THREE.Vector3(0, off, 0), new THREE.Vector3(sx, sy + off, sz)]
    return { points: p, mid: [sx / 2, sy / 2 + off, sz / 2], offset: off }
  }, [serverPosition])

  if (!serverPosition) return null

  const distPc = Math.sqrt(serverPosition.x ** 2 + serverPosition.y ** 2 + serverPosition.z ** 2)

  return (
    <group>
      <Line points={points} color="#a78bfa" lineWidth={2} dashed dashSize={2} gapSize={1.5} opacity={0.7} transparent />
      {/* short ticks linking the dimension line back to Earth and the server */}
      <Line points={[[0, 0, 0], [0, offset, 0]]} color="#a78bfa" lineWidth={1} opacity={0.4} transparent />
      <Line
        points={[[serverPosition.x, serverPosition.y, serverPosition.z], [serverPosition.x, serverPosition.y + offset, serverPosition.z]]}
        color="#a78bfa" lineWidth={1} opacity={0.4} transparent
      />
      <Html position={mid} center style={{ pointerEvents: 'none' }}>
        <span className="text-[10px] font-bold font-mono text-violet-300 bg-gray-950/80 px-1.5 py-0.5 rounded whitespace-nowrap">
          {distPc.toFixed(1)} {unit}
        </span>
      </Html>
    </group>
  )
}

// Concentric shells around Earth representing the gravitational well it sits
// in. Tighter near Earth, fading outward — Earth's clock runs slow here, which
// is exactly what gives a distant void server its relative time advantage.
const GRAVITY_WELL_RINGS = [
  { inner: 4, outer: 4.5, opacity: 0.30, speed: 0.2 },
  { inner: 7, outer: 7.4, opacity: 0.18, speed: -0.15 },
  { inner: 11, outer: 11.3, opacity: 0.10, speed: 0.1 },
  { inner: 16, outer: 16.2, opacity: 0.05, speed: -0.08 },
]

function GravityWell() {
  const ringsRef = useRef([])

  useFrame((_, delta) => {
    ringsRef.current.forEach((mesh, i) => {
      if (mesh) mesh.rotation.z += delta * GRAVITY_WELL_RINGS[i].speed
    })
  })

  return (
    <group position={[0, 0, 0]}>
      {GRAVITY_WELL_RINGS.map((r, i) => (
        <mesh
          key={i}
          ref={el => ringsRef.current[i] = el}
          rotation={[Math.PI / 2 + i * 0.3, 0, 0]}
        >
          <ringGeometry args={[r.inner, r.outer, 64]} />
          <meshBasicMaterial
            color="#f59e0b"
            transparent
            opacity={r.opacity}
            side={THREE.DoubleSide}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}
    </group>
  )
}

function ServerMarker({ position }) {
  const ringRef = useRef()

  useFrame((_, delta) => {
    if (ringRef.current) ringRef.current.rotation.z += delta * 0.3
  })

  if (!position) return null

  return (
    <group position={[position.x, position.y, position.z]}>
      <Float speed={2} floatIntensity={0.5} rotationIntensity={0.2}>
        <mesh>
          <sphereGeometry args={[2, 32, 32]} />
          <meshStandardMaterial
            color="#06b6d4"
            emissive="#06b6d4"
            emissiveIntensity={0.4}
            transparent
            opacity={0.85}
          />
        </mesh>
      </Float>
      <mesh ref={ringRef} rotation={[Math.PI / 3, 0, 0]}>
        <ringGeometry args={[3.5, 4, 64]} />
        <meshBasicMaterial color="#06b6d4" transparent opacity={0.25} side={THREE.DoubleSide} />
      </mesh>
      <Sparkles count={20} size={1.5} scale={8} speed={0.3} color="#06b6d4" />
    </group>
  )
}

function BackgroundSphere({ bgRadius }) {
  const material = useMemo(() => {
    return new THREE.ShaderMaterial({
      side: THREE.BackSide,
      uniforms: {},
      vertexShader: `
        varying vec3 vPosition;
        void main() {
          vPosition = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      // The divisor MUST match the sphere radius so the gradient maps from
      // center (0) to the sphere surface (1).
      fragmentShader: `
        varying vec3 vPosition;
        void main() {
          float dist = length(vPosition) / ${bgRadius.toFixed(1)};
          vec3 center = vec3(0.02, 0.04, 0.08);
          vec3 edge = vec3(0.008, 0.012, 0.03);
          gl_FragColor = vec4(mix(center, edge, dist), 1.0);
        }
      `,
    })
  }, [bgRadius])

  return (
    <mesh material={material}>
      <sphereGeometry args={[bgRadius, 32, 32]} />
    </mesh>
  )
}

function CameraController({ serverPosition }) {
  const { camera } = useThree()
  const target = useRef(null)
  const active = useRef(false)

  useEffect(() => {
    if (!serverPosition) return
    const sv = new THREE.Vector3(serverPosition.x, serverPosition.y, serverPosition.z)
    const midpoint = sv.clone().multiplyScalar(0.5)
    const dist = sv.length()
    const offset = new THREE.Vector3(0, dist * 0.6, dist * 1.2)
    target.current = midpoint.clone().add(offset)
    active.current = true
  }, [serverPosition])

  useFrame(() => {
    if (!active.current || !target.current) return
    camera.position.lerp(target.current, 0.04)
    if (camera.position.distanceTo(target.current) < 1) active.current = false
  })

  return null
}

function webglAvailable() {
  try {
    const canvas = document.createElement('canvas')
    return !!(window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')))
  } catch {
    return false
  }
}

const CLICK_DRAG_THRESHOLD_PX = 5

// `scene` defaults to SHARED_SCENE (the solar/cosmic constants, single source of
// truth in FarFutureView) so any caller that omits it renders identically.
// `scale` selects the point-cloud renderer: 'deepfield' streams LOD tiles via
// <DeepField> from `assetBase`; solar/cosmic render the catalog <StarField>.
export default function GalaxyMap({ stars, serverPosition, onPlaceServer, unit = 'pc', originLabel = 'Earth', scene = SHARED_SCENE, scale = 'solar', assetBase }) {
  const pointerDown = useRef(null)

  const handlePointerDown = (e) => {
    pointerDown.current = { x: e.clientX, y: e.clientY }
  }

  const handlePointerUp = (e) => {
    if (!onPlaceServer || !pointerDown.current) return
    const dx = e.clientX - pointerDown.current.x
    const dy = e.clientY - pointerDown.current.y
    pointerDown.current = null
    // A drag (used to orbit the camera) moves the pointer; only a near-stationary
    // press counts as a click that places/moves the server.
    if (Math.hypot(dx, dy) > CLICK_DRAG_THRESHOLD_PX) return
    onPlaceServer({ x: e.point.x, y: e.point.y, z: e.point.z })
  }

  if (!webglAvailable()) {
    return (
      <div className="w-full h-[440px] rounded-xl border border-gray-800 flex items-center justify-center p-6">
        <div className="max-w-md text-sm text-gray-400 space-y-3">
          <p className="text-gray-300 font-medium">The 3D galaxy map needs WebGL, which this browser can't currently create.</p>
          <p>To enable it in Chrome:</p>
          <ol className="list-decimal list-inside space-y-1 text-gray-500 text-xs">
            <li>Open <span className="font-mono text-cyan-400">chrome://settings/system</span> and turn on "Use hardware acceleration when available", then relaunch.</li>
            <li>If that doesn't work (e.g. no GPU), open <span className="font-mono text-cyan-400">chrome://flags</span>, set "Override software rendering list" to <span className="text-gray-300">Enabled</span>, and relaunch — this lets Chrome render WebGL in software.</li>
            <li>Verify at <span className="font-mono text-cyan-400">chrome://gpu</span> that "WebGL" shows as enabled.</li>
          </ol>
          <p className="text-gray-500 text-xs">The metrics panel still works without WebGL — deploy a server using the form.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative w-full h-[440px] rounded-xl border border-gray-800 overflow-hidden">
      <div className="absolute top-2 left-3 z-10 text-[10px] font-mono text-gray-500 pointer-events-none">
        Click to place a server · drag to orbit · scroll to zoom
      </div>
      <Canvas
        camera={{ position: scene.cameraPosition, fov: 60 }}
        raycaster={{ params: { Points: { threshold: 1.5 } } }}
      >
        <BackgroundSphere bgRadius={scene.bgRadius} />
        <ambientLight intensity={0.3} />
        <pointLight position={[0, 100, 0]} intensity={0.2} color="#1e3a5f" />
        <Stars radius={scene.starsRadius} depth={scene.starsDepth} count={3000} factor={2} fade speed={0.3} saturation={0.1} />
        {scale === 'deepfield'
          ? <DeepField assetBase={assetBase} unit={unit} />
          : <StarField stars={stars} unit={unit} />}
        <GravityWell />
        <EarthMarker originLabel={originLabel} />
        <CommLine serverPosition={serverPosition} />
        <DistanceLine serverPosition={serverPosition} unit={unit} />
        <ServerMarker position={serverPosition} />
        <Grid
          cellSize={scene.gridCellSize}
          sectionSize={scene.gridSectionSize}
          cellColor="#1a2332"
          sectionColor="#0e4d6e"
          fadeDistance={scene.gridFadeDistance}
          fadeStrength={1.5}
          infiniteGrid
          cellThickness={0.3}
          sectionThickness={0.6}
        />
        <mesh visible={false} onPointerDown={handlePointerDown} onPointerUp={handlePointerUp}>
          <planeGeometry args={[scene.pickPlaneSize, scene.pickPlaneSize]} />
          <meshBasicMaterial side={THREE.DoubleSide} />
        </mesh>
        <CameraController serverPosition={serverPosition} />
        <OrbitControls enableDamping dampingFactor={0.1} rotateSpeed={0.45} />
      </Canvas>
    </div>
  )
}
