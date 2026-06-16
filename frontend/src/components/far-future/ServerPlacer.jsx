import { useState } from 'react'

export default function ServerPlacer({ onPlaceServer }) {
  const [distance, setDistance] = useState(10)
  const [longitude, setLongitude] = useState(0)
  const [latitude, setLatitude] = useState(0)

  const handleDeploy = async () => {
    try {
      const res = await fetch('/api/physics/cartesian', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ distance, longitude, latitude }),
      })
      const coords = await res.json()
      onPlaceServer(coords)
    } catch {
      // silent fail
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4">
      <h3 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider">Deploy Time Sink Server</h3>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Distance (pc)</label>
          <input
            type="number"
            min="0.1"
            step="1"
            value={distance}
            onChange={e => setDistance(Number(e.target.value))}
            className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm font-mono text-gray-100 focus:border-cyan-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Longitude (°)</label>
          <input
            type="number"
            min="0"
            max="360"
            step="1"
            value={longitude}
            onChange={e => setLongitude(Number(e.target.value))}
            className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm font-mono text-gray-100 focus:border-cyan-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Latitude (°)</label>
          <input
            type="number"
            min="-90"
            max="90"
            step="1"
            value={latitude}
            onChange={e => setLatitude(Number(e.target.value))}
            className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm font-mono text-gray-100 focus:border-cyan-500 focus:outline-none"
          />
        </div>
      </div>
      <button
        onClick={handleDeploy}
        className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-medium py-2 rounded-lg transition-colors"
      >
        Deploy Time Sink
      </button>
    </div>
  )
}
