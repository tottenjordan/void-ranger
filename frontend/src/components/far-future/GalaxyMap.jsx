import { useRef, useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

function StarField({ stars }) {
  const ref = useRef()

  const { positions, sizes } = useMemo(() => {
    const positions = new Float32Array(stars.length * 3)
    const sizes = new Float32Array(stars.length)
    stars.forEach((s, i) => {
      positions[i * 3] = s.x
      positions[i * 3 + 1] = s.y
      positions[i * 3 + 2] = s.z
      sizes[i] = s.size
    })
    return { positions, sizes }
  }, [stars])

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" array={positions} count={stars.length} itemSize={3} />
        <bufferAttribute attach="attributes-size" array={sizes} count={stars.length} itemSize={1} />
      </bufferGeometry>
      <pointsMaterial
        size={0.8}
        sizeAttenuation
        color="#e0e8ff"
        transparent
        opacity={0.8}
        depthWrite={false}
      />
    </points>
  )
}

function ServerMarker({ position }) {
  if (!position) return null
  return (
    <mesh position={[position.x, position.y, position.z]}>
      <sphereGeometry args={[2, 16, 16]} />
      <meshBasicMaterial color="#06b6d4" transparent opacity={0.7} />
    </mesh>
  )
}

export default function GalaxyMap({ stars, serverPosition, onPlaceServer }) {
  const handleClick = (e) => {
    if (!onPlaceServer) return
    const point = e.point
    onPlaceServer({ x: point.x, y: point.y, z: point.z })
  }

  return (
    <div className="w-full h-[500px] rounded-xl border border-gray-800 overflow-hidden">
      <Canvas camera={{ position: [0, 200, 400], fov: 60 }}>
        <color attach="background" args={['#030712']} />
        <ambientLight intensity={0.3} />
        <StarField stars={stars} />
        <ServerMarker position={serverPosition} />
        <polarGridHelper args={[500, 8, 8, 64, '#1f2937', '#1f2937']} />
        <mesh visible={false} onClick={handleClick}>
          <planeGeometry args={[2000, 2000]} />
          <meshBasicMaterial side={THREE.DoubleSide} />
        </mesh>
        <OrbitControls enableDamping dampingFactor={0.1} />
      </Canvas>
    </div>
  )
}
