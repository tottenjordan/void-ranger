import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Stars, PointMaterial, Float, Sparkles, Grid } from '@react-three/drei'
import * as THREE from 'three'

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
        <OrbitControls enableDamping dampingFactor={0.1} />
      </Canvas>
    </div>
  )
}
