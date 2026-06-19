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

// Controlled by the parent so a map-click placement can update these inputs and
// the values persist while the popover is closed.
export default function ServerPlacer({ onPlaceServer, onDone, coords, onCoordsChange, unit = 'pc' }) {
  const { distance, longitude, latitude } = coords
  const setField = (key, value) => onCoordsChange({ ...coords, [key]: value })

  const handleDeploy = async () => {
    try {
      const res = await fetch('/api/physics/cartesian', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ distance, longitude, latitude }),
      })
      const coords = await res.json()
      onPlaceServer(coords)
      onDone?.()
    } catch {
      // silent fail
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500 leading-relaxed">
        Choose where in the void to place a server. Position sets the light-speed
        communication latency; farther is slower.
      </p>
      <div className="grid grid-cols-3 gap-3">
        <Field
          label={`Distance (${unit})`}
          hint={`Distance from origin in ${unit}. Drives round-trip latency.`}
          tooltip={`How far the server sits from the origin, in ${unit}. This is the only field that affects communication latency: round-trip delay = 2 × distance ÷ c.`}
        >
          <input type="number" min="0.1" step="1" value={distance}
            onChange={e => setField('distance', Number(e.target.value))} className={inputCls} />
        </Field>
        <Field
          label="Longitude (°)"
          hint="Galactic longitude, 0–360°. Direction only."
          tooltip="Galactic longitude (0–360°): the compass direction around the galactic plane. Affects placement direction, not distance or latency."
        >
          <input type="number" min="0" max="360" step="1" value={longitude}
            onChange={e => setField('longitude', Number(e.target.value))} className={inputCls} />
        </Field>
        <Field
          label="Latitude (°)"
          hint="Galactic latitude, −90 to 90°. Direction only."
          tooltip="Galactic latitude (−90 to 90°): angle above or below the galactic plane. Affects placement direction, not distance or latency."
        >
          <input type="number" min="-90" max="90" step="1" value={latitude}
            onChange={e => setField('latitude', Number(e.target.value))} className={inputCls} />
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
    </div>
  )
}
