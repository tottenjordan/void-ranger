import { useState, useEffect, useCallback } from 'react'
import GalaxyMap from './GalaxyMap'
import ServerPlacer from './ServerPlacer'
import MetricsDash from './MetricsDash'
import { commaInt, parseSecondsInput } from '../../utils/format'

const LEGEND_ITEMS = [
  { swatch: 'dot', color: '#22c55e', label: 'Earth', desc: 'Deep in a gravitational well — its clock runs slow.' },
  { swatch: 'ring', color: '#f59e0b', label: 'Gravity well', desc: "Shells around Earth showing the field that slows its clock." },
  { swatch: 'dot', color: '#06b6d4', label: 'Cosmic Server', desc: 'The deployed server, in weak gravity where its clock runs fast (the time advantage).' },
  { swatch: 'ring', color: '#06b6d4', label: 'Orbit marker', desc: 'Ring + sparkles marking the deployed server.' },
  { swatch: 'line', color: '#ef4444', label: 'Comm link', desc: 'Light-speed channel (red) between Earth and the server; its label shows the round-trip time.' },
  { swatch: 'dot', color: '#ef4444', label: 'Signal pulse', desc: 'The message packet traveling the round-trip link at light speed.' },
  { swatch: 'line', color: '#a78bfa', label: 'Distance', desc: 'Straight-line Earth↔server distance in parsecs.' },
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
        Earth's slow clock (deep in the dense solar neighborhood) and the server's clock, whose
        rate depends on the gravity of stars near where you place it. Deep voids run fastest;
        placing the server near a star slows it down. Farther placements also add round-trip light
        delay — the tradeoff the metrics above quantify.
      </p>
    </div>
  )
}

function BreakevenLine({ breakeven, taskSeconds }) {
  if (breakeven === undefined) return null // no server placed yet
  const title = "Smallest task whose time-dilation savings cover the round-trip light delay at this location. Tasks larger than this net a gain; smaller ones net a loss."
  if (breakeven === null) {
    return (
      <p className="text-center text-[11px] italic text-gray-500 mt-1" title={title}>
        Breakeven: <span className="text-red-400 not-italic">none — no time advantage here</span>
      </p>
    )
  }
  const winning = taskSeconds >= breakeven
  return (
    <p className="text-center text-[11px] italic text-gray-500 mt-1" title={title}>
      Breakeven workload:{' '}
      <span className={`not-italic font-mono ${winning ? 'text-green-400' : 'text-red-400'}`}>
        {commaInt(breakeven)} s
      </span>
    </p>
  )
}

function TaskField({ taskSeconds, onTaskSecondsChange, breakeven }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <label
        className="block text-center text-xs text-gray-400 uppercase tracking-wider mb-2"
        title="Workload size: compute-seconds measured on the running machine's own clock."
      >
        Task Workload Size (s)
      </label>
      {/* Value is derived from state: empty input is ignored (field can't be
          blanked) and comma reformatting may push the caret to the end on
          mid-string edits — acceptable for this short numeric field. */}
      <input
        type="text"
        inputMode="numeric"
        value={commaInt(taskSeconds)}
        onChange={e => {
          const v = parseSecondsInput(e.target.value)
          if (v !== null) onTaskSecondsChange(v)
        }}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-center text-lg font-mono text-gray-100 focus:border-cyan-500 focus:outline-none"
      />
      <p className="text-center text-[11px] italic text-gray-500 mt-2 leading-tight">
        This is the processing time for a program on a given server.
      </p>
      <BreakevenLine breakeven={breakeven} taskSeconds={taskSeconds} />
    </div>
  )
}

export default function FarFutureView({ taskSeconds, onTaskSecondsChange }) {
  const [stars, setStars] = useState([])
  const [serverPosition, setServerPosition] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [panelOpen, setPanelOpen] = useState(true)

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
        }),
      })
      setMetrics(await res.json())
    } catch {
      setMetrics(null)
    }
  }, [taskSeconds])

  // Re-run the efficiency calc when the task size changes. Deps intentionally
  // omit placeServer/serverPosition: placeServer is already useCallback'd on
  // taskSeconds (so the closure is current), and serverPosition changes post
  // via placeServer directly — listing them here would double-post.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (serverPosition) placeServer(serverPosition)
  }, [taskSeconds])

  if (loading) {
    return <p className="text-gray-500 text-center py-20 font-mono">Loading star field...</p>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row gap-6">
        <div className="flex-1 min-w-0">
          <GalaxyMap stars={stars} serverPosition={serverPosition} onPlaceServer={placeServer} />
        </div>
        {panelOpen ? (
          <div className="lg:w-80 flex-shrink-0 space-y-6">
            <div className="flex justify-end">
              <button onClick={() => setPanelOpen(false)} title="Collapse panel"
                className="text-gray-500 hover:text-cyan-400 text-sm">▶ collapse</button>
            </div>
            <TaskField taskSeconds={taskSeconds} onTaskSecondsChange={onTaskSecondsChange}
              breakeven={metrics ? metrics.breakeven_task_seconds : undefined} />
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
        ) : (
          <button onClick={() => setPanelOpen(true)} title="Expand controls"
            className="lg:w-8 flex-shrink-0 flex items-start justify-center pt-2 text-gray-500 hover:text-cyan-400">
            ◀
          </button>
        )}
      </div>
      {metrics && (
        <MetricsDash
          distancePc={serverPosition
            ? Math.sqrt(serverPosition.x ** 2 + serverPosition.y ** 2 + serverPosition.z ** 2)
            : 0}
          clockAdvantage={metrics.clock_advantage}
          earthComputeTime={metrics.earth_compute_time}
          earthWaitTime={metrics.earth_wait_time}
          communicationCost={metrics.latency_seconds}
          netGain={metrics.net_gain}
        />
      )}
      <MapLegend />
    </div>
  )
}
