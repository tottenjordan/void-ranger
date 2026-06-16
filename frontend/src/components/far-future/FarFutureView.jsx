import { useState, useEffect, useCallback } from 'react'
import GalaxyMap from './GalaxyMap'
import ServerPlacer from './ServerPlacer'
import MetricsDash from './MetricsDash'

// Earth's gravitational environment — exaggerated for educational visibility.
// Models Earth orbiting close to a solar-mass object so the dilation effect
// is large enough to see in the dashboard. Real Sun-Earth dilation is ~1e-8.
const DEFAULT_MASS_KG = 1.989e30   // solar mass
const DEFAULT_RADIUS_M = 3e4       // 30 km — near neutron-star surface

const LEGEND_ITEMS = [
  { swatch: 'dot', color: '#22c55e', label: 'Earth', desc: 'Deep in a gravitational well — its clock runs slow.' },
  { swatch: 'ring', color: '#f59e0b', label: 'Gravity well', desc: "Shells around Earth showing the field that slows its clock." },
  { swatch: 'dot', color: '#06b6d4', label: 'Void server', desc: 'In weak gravity — its clock runs fast (the time advantage).' },
  { swatch: 'ring', color: '#06b6d4', label: 'Orbit marker', desc: 'Ring + sparkles marking the deployed server.' },
  { swatch: 'line', color: '#06b6d4', label: 'Comm link', desc: 'Light-speed channel between Earth and the server.' },
  { swatch: 'dot', color: '#ef4444', label: 'Signal pulse', desc: 'A message traveling the round trip at light speed.' },
]

function Swatch({ type, color }) {
  if (type === 'ring') {
    return <span className="inline-block w-3 h-3 rounded-full border-2 flex-shrink-0" style={{ borderColor: color }} />
  }
  if (type === 'line') {
    return <span className="inline-block w-3 h-0.5 flex-shrink-0" style={{ backgroundColor: color }} />
  }
  return <span className="inline-block w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
}

function MapLegend() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Map Key</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2">
        {LEGEND_ITEMS.map(item => (
          <div key={item.label} className="flex items-start gap-2">
            <span className="mt-1"><Swatch type={item.swatch} color={item.color} /></span>
            <p className="text-xs text-gray-400 leading-tight">
              <span className="text-gray-200 font-medium">{item.label}</span> — {item.desc}
            </p>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-gray-600 mt-3 leading-relaxed">
        Time dilation comes from the <span className="text-amber-400">difference</span> between
        Earth's slow clock (deep in the gravity well) and the server's fast clock (in the void).
        Placing the server farther away increases that round-trip light delay — the tradeoff the
        metrics above quantify.
      </p>
    </div>
  )
}

export default function FarFutureView({ taskSeconds }) {
  const [stars, setStars] = useState([])
  const [serverPosition, setServerPosition] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/stars')
      .then(res => res.json())
      .then(data => { setStars(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const placeServer = useCallback(async (coords) => {
    setServerPosition(coords)
    try {
      const res = await fetch('/api/physics/efficiency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          x: coords.x,
          y: coords.y,
          z: coords.z,
          task_seconds: taskSeconds,
          mass_kg: DEFAULT_MASS_KG,
          radius_m: DEFAULT_RADIUS_M,
        }),
      })
      setMetrics(await res.json())
    } catch {
      setMetrics(null)
    }
  }, [taskSeconds])

  useEffect(() => {
    if (serverPosition) placeServer(serverPosition)
  }, [taskSeconds])

  if (loading) {
    return <p className="text-gray-500 text-center py-20 font-mono">Loading star field...</p>
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <GalaxyMap stars={stars} serverPosition={serverPosition} onPlaceServer={placeServer} />
        </div>
        <div className="space-y-6">
          <ServerPlacer onPlaceServer={placeServer} />
          {serverPosition && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Server Position</p>
              <p className="text-sm font-mono text-gray-300">
                ({serverPosition.x.toFixed(1)}, {serverPosition.y.toFixed(1)}, {serverPosition.z.toFixed(1)}) pc
              </p>
            </div>
          )}
        </div>
      </div>
      {metrics && (
        <MetricsDash
          earthComputeTime={metrics.earth_compute_time}
          earthWaitTime={metrics.earth_wait_time}
          netGain={metrics.net_gain}
        />
      )}
      <MapLegend />
    </div>
  )
}
