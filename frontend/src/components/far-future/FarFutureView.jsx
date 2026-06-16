import { useState, useEffect, useCallback } from 'react'
import GalaxyMap from './GalaxyMap'
import ServerPlacer from './ServerPlacer'
import MetricsDash from './MetricsDash'

const DEFAULT_MASS_KG = 1.989e30
const DEFAULT_RADIUS_M = 1e10

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
          localTime={metrics.local_time}
          earthWaitTime={metrics.earth_wait_time}
          netGain={metrics.net_gain}
        />
      )}
    </div>
  )
}
