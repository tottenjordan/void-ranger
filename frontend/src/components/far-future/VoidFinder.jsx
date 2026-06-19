import { useState } from 'react'
import { SCALE_UI } from './FarFutureView'

const inputCls =
  'w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm font-mono text-gray-100 focus:border-cyan-500 focus:outline-none'

// Auto-placement card: searches the backend for a good spot and drops the server
// there (the parent's onPlaceServer handles metrics + camera fly-to).
export default function VoidFinder({ onPlaceServer, taskSeconds, onDone, scale = 'solar' }) {
  const ui = SCALE_UI[scale]
  const [radius, setRadius] = useState(ui.defaultRadius)
  const [searching, setSearching] = useState(false)

  const findSpot = async (endpoint, body) => {
    setSearching(true)
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const coords = await res.json()
      setSearching(false) // clear before onDone (which may unmount this card)
      onPlaceServer(coords)
      onDone?.()
    } catch {
      setSearching(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500 leading-relaxed">
        Let the app search within a radius for a good placement.
      </p>
      <div>
        <label
          className="block text-xs text-gray-400 mb-1"
          title="Caps how far from Earth the search looks. The cap is a latency budget — it does not change the gravity; the search evaluates every star's pull to find the emptiest pocket."
        >
          Search radius ({ui.unit})
        </label>
        <input type="number" min="1" step="10" value={radius}
          onChange={e => setRadius(Number(e.target.value))} className={inputCls} />
        <p className="text-[10px] text-gray-600 mt-1 leading-tight">
          How far out to look. Larger = emptier voids, but more latency.
        </p>
      </div>
      <button
        onClick={() => findSpot('/api/physics/best-void', { max_distance_pc: radius, scale })}
        disabled={searching}
        title="Find the lowest-gravity spot within the radius — the emptiest pocket, farthest from all stars, where the clock runs fastest."
        className="w-full bg-gray-800 hover:bg-gray-700 border border-cyan-700 text-cyan-300 font-medium py-2 rounded-lg transition-colors disabled:opacity-50"
      >
        {searching ? 'Searching…' : 'Find deepest void'}
      </button>
      <button
        onClick={() => findSpot('/api/physics/best-spot', { task_seconds: taskSeconds, max_distance_pc: radius, scale })}
        disabled={searching}
        title="Find the spot that maximizes net gain — balances the void's clock advantage against light-delay latency for your current Task Workload Size."
        className="w-full bg-gray-800 hover:bg-gray-700 border border-green-700 text-green-300 font-medium py-2 rounded-lg transition-colors disabled:opacity-50"
      >
        {searching ? 'Searching…' : 'Best spot for this task'}
      </button>
    </div>
  )
}
