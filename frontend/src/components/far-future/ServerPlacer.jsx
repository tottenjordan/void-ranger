import { useState } from 'react'

function Field({ label, hint, tooltip, children }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1" title={tooltip}>{label}</label>
      {children}
      <p className="text-[10px] text-gray-600 mt-1 leading-tight">{hint}</p>
    </div>
  )
}

const inputCls =
  'w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm font-mono text-gray-100 focus:border-cyan-500 focus:outline-none'

export default function ServerPlacer({ onPlaceServer, taskSeconds }) {
  const [distance, setDistance] = useState(10)
  const [longitude, setLongitude] = useState(0)
  const [latitude, setLatitude] = useState(0)
  const [radius, setRadius] = useState(300)
  const [searching, setSearching] = useState(false)

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

  // Ask the backend to search for a placement, then drop the server there (the
  // existing onPlaceServer flow handles metrics + camera fly-to).
  const findSpot = async (endpoint, body) => {
    setSearching(true)
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      onPlaceServer(await res.json())
    } catch {
      // silent fail
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4">
      <h3 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider">Deploy Cosmic Server</h3>
      <p className="text-xs text-gray-500 leading-relaxed">
        Choose where in the void to place a server. Position sets the light-speed
        communication latency; farther is slower.
      </p>
      <div className="grid grid-cols-3 gap-3">
        <Field
          label="Distance (pc)"
          hint="Parsecs from Earth (1 pc ≈ 3.26 ly). Drives round-trip latency."
          tooltip="How far the server sits from Earth, in parsecs. This is the only field that affects communication latency: round-trip delay = 2 × distance ÷ c."
        >
          <input type="number" min="0.1" step="1" value={distance}
            onChange={e => setDistance(Number(e.target.value))} className={inputCls} />
        </Field>
        <Field
          label="Longitude (°)"
          hint="Galactic longitude, 0–360°. Direction only."
          tooltip="Galactic longitude (0–360°): the compass direction around the galactic plane. Affects placement direction, not distance or latency."
        >
          <input type="number" min="0" max="360" step="1" value={longitude}
            onChange={e => setLongitude(Number(e.target.value))} className={inputCls} />
        </Field>
        <Field
          label="Latitude (°)"
          hint="Galactic latitude, −90 to 90°. Direction only."
          tooltip="Galactic latitude (−90 to 90°): angle above or below the galactic plane. Affects placement direction, not distance or latency."
        >
          <input type="number" min="-90" max="90" step="1" value={latitude}
            onChange={e => setLatitude(Number(e.target.value))} className={inputCls} />
        </Field>
      </div>
      <button
        onClick={handleDeploy}
        title="Convert these galactic coordinates to a 3D position and place the server there."
        className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-medium py-2 rounded-lg transition-colors"
      >
        Deploy Cosmic Server
      </button>
      <p className="text-[10px] text-gray-600 leading-tight">
        Tip: you can also click anywhere in the galaxy map to place a server.
      </p>

      <div className="border-t border-gray-800 pt-4 space-y-3">
        <p className="text-xs text-gray-500 leading-relaxed">
          Or let the app find a spot within a search radius:
        </p>
        <Field
          label="Search radius (pc)"
          hint="How far out to look. Larger = emptier voids, but more latency."
          tooltip="Caps how far from Earth the search looks. The cap is a latency budget — it does not change the gravity; the search evaluates every star's pull to find the emptiest pocket."
        >
          <input type="number" min="1" step="10" value={radius}
            onChange={e => setRadius(Number(e.target.value))} className={inputCls} />
        </Field>
        <button
          onClick={() => findSpot('/api/physics/best-void', { max_distance_pc: radius })}
          disabled={searching}
          title="Find the lowest-gravity spot within the radius — the emptiest pocket, farthest from all stars, where the clock runs fastest."
          className="w-full bg-gray-800 hover:bg-gray-700 border border-cyan-700 text-cyan-300 font-medium py-2 rounded-lg transition-colors disabled:opacity-50"
        >
          {searching ? 'Searching…' : 'Find deepest void'}
        </button>
        <button
          onClick={() => findSpot('/api/physics/best-spot', { task_seconds: taskSeconds, max_distance_pc: radius })}
          disabled={searching}
          title="Find the spot that maximizes net gain — balances the void's clock advantage against light-delay latency for your current Task Workload Size."
          className="w-full bg-gray-800 hover:bg-gray-700 border border-green-700 text-green-300 font-medium py-2 rounded-lg transition-colors disabled:opacity-50"
        >
          {searching ? 'Searching…' : 'Best spot for this task'}
        </button>
      </div>
    </div>
  )
}
