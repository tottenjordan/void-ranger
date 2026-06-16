import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Stars, PointMaterial, Float, Sparkles, Grid, Html, Line } from '@react-three/drei'
import * as THREE from 'three'

const PARSEC_KM = 3.086e13
const C_KM_S = 299792.458

function StarField({ stars }) {
  const ref = useRef()

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
    if (ref.current) ref.current.rotation.y += delta * 0.005
  })

  return (
    <points ref={ref}>
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
  )
}

function EarthMarker() {
  return (
    <group position={[0, 0, 0]}>
      <mesh>
        <sphereGeometry args={[1.5, 16, 16]} />
        <meshStandardMaterial color="#22c55e" emissive="#22c55e" emissiveIntensity={0.3} />
      </mesh>
      <Html position={[0, 4, 0]} center style={{ pointerEvents: 'none' }}>
        <span className="text-[10px] font-mono text-green-400 bg-gray-950/80 px-1.5 py-0.5 rounded whitespace-nowrap">
          Earth
        </span>
      </Html>
    </group>
  )
}

function formatLatency(seconds) {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)} hr`
  if (seconds < 31536000) return `${(seconds / 86400).toFixed(1)} days`
  return `${(seconds / 31536000).toFixed(1)} yr`
}

function CommLine({ serverPosition }) {
  if (!serverPosition) return null

  const distPc = Math.sqrt(serverPosition.x ** 2 + serverPosition.y ** 2 + serverPosition.z ** 2)
  const roundTripSeconds = (2 * distPc * PARSEC_KM) / C_KM_S
  const pulseRef = useRef()

  const points = useMemo(() => [
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(serverPosition.x, serverPosition.y, serverPosition.z),
  ], [serverPosition])

  useFrame(({ clock }) => {
    if (!pulseRef.current) return
    const t = (clock.getElapsedTime() % 4) / 4
    const ping = t < 0.5 ? t * 2 : 2 - t * 2
    pulseRef.current.position.lerpVectors(points[0], points[1], ping)
  })

  return (
    <group>
      <Line
        points={points}
        color="#06b6d4"
        lineWidth={1}
        dashed
        dashSize={3}
        gapSize={2}
        opacity={0.4}
        transparent
      />
      <mesh ref={pulseRef}>
        <sphereGeometry args={[0.8, 8, 8]} />
        <meshBasicMaterial color="#06b6d4" />
      </mesh>
      <Html
        position={[serverPosition.x, serverPosition.y + 5, serverPosition.z]}
        center
        style={{ pointerEvents: 'none' }}
      >
        <span className="text-[10px] font-mono text-cyan-400 bg-gray-950/80 px-1.5 py-0.5 rounded whitespace-nowrap">
          {distPc.toFixed(1)} pc | RTT {formatLatency(roundTripSeconds)}
        </span>
      </Html>
    </group>
  )
}

function GravityRings({ position }) {
  if (!position) return null
  const ringsRef = useRef([])

  const rings = [
    { inner: 4, outer: 4.5, opacity: 0.25, speed: 0.2 },
    { inner: 7, outer: 7.4, opacity: 0.15, speed: -0.15 },
    { inner: 11, outer: 11.3, opacity: 0.08, speed: 0.1 },
    { inner: 16, outer: 16.2, opacity: 0.04, speed: -0.08 },
  ]

  useFrame((_, delta) => {
    ringsRef.current.forEach((mesh, i) => {
      if (mesh) mesh.rotation.z += delta * rings[i].speed
    })
  })

  return (
    <group position={[position.x, position.y, position.z]}>
      {rings.map((r, i) => (
        <mesh
          key={i}
          ref={el => ringsRef.current[i] = el}
          rotation={[Math.PI / 2 + i * 0.3, 0, 0]}
        >
          <ringGeometry args={[r.inner, r.outer, 64]} />
          <meshBasicMaterial
            color="#06b6d4"
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
  if (!position) return null
  const ringRef = useRef()

  useFrame((_, delta) => {
    if (ringRef.current) ringRef.current.rotation.z += delta * 0.3
  })

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

function BackgroundSphere() {
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
      fragmentShader: `
        varying vec3 vPosition;
        void main() {
          float dist = length(vPosition) / 900.0;
          vec3 center = vec3(0.02, 0.04, 0.08);
          vec3 edge = vec3(0.008, 0.012, 0.03);
          gl_FragColor = vec4(mix(center, edge, dist), 1.0);
        }
      `,
    })
  }, [])

  return (
    <mesh material={material}>
      <sphereGeometry args={[900, 32, 32]} />
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

export default function GalaxyMap({ stars, serverPosition, onPlaceServer }) {
  const handleClick = (e) => {
    if (!onPlaceServer) return
    onPlaceServer({ x: e.point.x, y: e.point.y, z: e.point.z })
  }

  return (
    <div className="w-full h-[500px] rounded-xl border border-gray-800 overflow-hidden">
      <Canvas camera={{ position: [0, 200, 400], fov: 60 }}>
        <BackgroundSphere />
        <ambientLight intensity={0.3} />
        <pointLight position={[0, 100, 0]} intensity={0.2} color="#1e3a5f" />
        <Stars radius={800} depth={200} count={3000} factor={2} fade speed={0.3} saturation={0.1} />
        <StarField stars={stars} />
        <EarthMarker />
        <CommLine serverPosition={serverPosition} />
        <GravityRings position={serverPosition} />
        <ServerMarker position={serverPosition} />
        <Grid
          cellSize={50}
          sectionSize={200}
          cellColor="#1a2332"
          sectionColor="#0e4d6e"
          fadeDistance={600}
          fadeStrength={1.5}
          infiniteGrid
          cellThickness={0.3}
          sectionThickness={0.6}
        />
        <mesh visible={false} onClick={handleClick}>
          <planeGeometry args={[2000, 2000]} />
          <meshBasicMaterial side={THREE.DoubleSide} />
        </mesh>
        <CameraController serverPosition={serverPosition} />
        <OrbitControls enableDamping dampingFactor={0.1} />
      </Canvas>
    </div>
  )
}
