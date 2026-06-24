import { useState, useEffect, useCallback } from 'react'
import GalaxyMap from './GalaxyMap'
import ServerPlacer from './ServerPlacer'
import VoidFinder from './VoidFinder'
import Popover from './Popover'
import MetricsDash from './MetricsDash'
import { daysLabel, yearsLabel, yearsInput, parseYearsInput, relatableDuration, cartesianToGalactic } from '../../utils/format'

// Per-scale UI config. Units, nouns, the catalog endpoint, defaults and labels
// differ per scale. Each entry also carries a `scene` object with the 3D scene
// constants consumed by <GalaxyMap>. Solar and cosmic deliberately share the
// same scene numbers (galaxy Mpc coords span the same numeric range as star pc
// coords); Deep Field uses a larger volume for the ±500 Mpc cube.
export const SHARED_SCENE = {
  cameraPosition: [0, 200, 400],
  bgRadius: 900,
  starsRadius: 800,
  starsDepth: 200,
  gridCellSize: 50,
  gridSectionSize: 200,
  gridFadeDistance: 600,
  pickPlaneSize: 2000,
}

export const SCALE_UI = {
  solar: {
    unit: 'pc',
    originLabel: 'Earth',
    objectNoun: 'star',
    endpoint: '/api/stars',
    defaultRadius: 300,
    toggleLabel: 'Solar Neighborhood',
    scene: SHARED_SCENE,
  },
  cosmic: {
    unit: 'Mpc',
    // Keep "Earth" as the origin noun at both scales for consistency with the
    // metric cards ("Earth Compute Time" …) and the plain-language summary. At
    // cosmic scale Earth is our vantage point inside the Milky Way; the
    // Milky-Way framing is explained in docs/cosmic-web.md.
    originLabel: 'Earth',
    objectNoun: 'galaxy',
    endpoint: '/api/galaxies',
    defaultRadius: 150,
    toggleLabel: 'Cosmic Web',
    scene: SHARED_SCENE,
  },
  deepfield: {
    unit: 'Mpc',
    originLabel: 'Earth',
    objectNoun: 'galaxy',
    // Deep Field has NO catalog API: galaxies stream as LOD tiles in 2E.2 from
    // assetBase, not from /api/*. A null endpoint tells the catalog effect to
    // skip the fetch.
    endpoint: null,
    defaultRadius: 300,
    toggleLabel: 'Deep Field',
    // Base URL for streamed LOD tiles (overridable for a production CDN via the
    // VITE_ASSET_BASE_URL env var). Consumed by the streamer in 2E.2.
    assetBase: import.meta.env.VITE_ASSET_BASE_URL ?? '/deepfield',
    // Larger scene for the ±500 Mpc volume (corner distance ≈ 866; default
    // deploy radius 300) so the cube fits the frame and the pick-plane covers
    // all clickable space.
    scene: {
      cameraPosition: [0, 350, 700],
      bgRadius: 1600,
      starsRadius: 1400,
      starsDepth: 400,
      gridCellSize: 100,
      gridSectionSize: 500,
      gridFadeDistance: 1200,
      pickPlaneSize: 4000,
    },
  },
}

const LEGEND_ITEMS = [
  { swatch: 'dot', color: '#22c55e', label: 'Earth', desc: 'Deep in the gravity well of our dense solar-neighborhood.' },
  { swatch: 'ring', color: '#f59e0b', label: 'Gravity well', desc: 'Shells around Earth showing the gravitational field that slows the clock.' },
  { swatch: 'dot', color: '#06b6d4', label: 'Cosmic Server', desc: 'The deployed server, in weak gravity where its clock runs fast (the time advantage).' },
  { swatch: 'ring', color: '#06b6d4', label: 'Orbit marker', desc: 'Decorative cyan ring + sparkles that highlight where the Cosmic Server sits in the star field — a locator, not a real orbit.' },
  { swatch: 'line', color: '#ef4444', label: 'Comm link', desc: 'Light-speed channel (red) between Earth and the server; its label shows the round-trip time.' },
  { swatch: 'dot', color: '#ef4444', label: 'Signal pulse', desc: 'The message packet traveling the round-trip link at light speed.' },
  { swatch: 'line', color: '#a78bfa', label: 'Distance', desc: 'Straight-line Earth↔server distance in parsecs. Drawn as an offset dimension line (parallel above the comm link, with tick marks) so it never overlaps the signal path; the offset grows with distance.' },
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

// Plain-language "so what?" translation of the metrics into relatable units,
// with an optional "Show the math" breakdown computed from the live values.
function PlainSummary({ taskSeconds, metrics }) {
  const [showMath, setShowMath] = useState(false)
  if (!metrics || metrics.earth_compute_time == null) return null
  const compute = metrics.earth_compute_time
  const wait = metrics.earth_wait_time
  const comm = metrics.latency_seconds
  const net = metrics.net_gain
  const fe = metrics.earth_dilation_factor
  const fs = metrics.server_dilation_factor
  const adv = metrics.clock_advantage
  const ratio = fe / fs
  const be = metrics.breakeven_task_seconds
  const faster = adv > 1
  const saves = net >= 0
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">In plain terms</p>
      <p className="text-sm text-gray-300 leading-relaxed">
        Running this job <span className="text-green-400 font-medium">on Earth</span> would take{' '}
        <span className="font-mono text-green-400">{relatableDuration(taskSeconds)}</span>. Offloaded to the{' '}
        <span className="text-cyan-400 font-medium">Cosmic Server</span>, the same computation takes{' '}
        <span className="font-mono text-green-400">{relatableDuration(compute)}</span> of Earth time
        (its clock runs {faster ? 'faster' : 'slower'} than ours), plus{' '}
        <span className="font-mono text-red-400">{relatableDuration(comm)}</span> waiting for the round-trip
        signal — a total wait of{' '}
        <span className="font-mono text-amber-400">{relatableDuration(wait)}</span>.{' '}
        {saves ? (
          <>Net result: you <span className="text-green-400 font-medium">save {relatableDuration(Math.abs(net))}</span> versus computing at home.</>
        ) : (
          <>Net result: you <span className="text-red-400 font-medium">lose {relatableDuration(Math.abs(net))}</span> — not worth offloading from here.</>
        )}
      </p>
      <button
        onClick={() => setShowMath(m => !m)}
        className="mt-3 text-[11px] text-cyan-400 hover:text-cyan-300 uppercase tracking-wider"
      >
        {showMath ? '▾ Hide the math' : '▸ Show the math'}
      </button>
      {showMath && (
        <div className="mt-2 border-t border-gray-800 pt-3 font-mono text-[11px] text-gray-400 leading-relaxed space-y-1 overflow-x-auto">
          <div><span className="text-cyan-400">Clock advantage</span> = f_server / f_earth = {fs.toFixed(5)} / {fe.toFixed(5)} = {adv.toFixed(4)}×</div>
          <div><span className="text-green-400">Earth Compute</span> = task × (f_earth / f_server) = {yearsLabel(taskSeconds)} × {ratio.toFixed(5)} ≈ {yearsLabel(compute)}</div>
          <div><span className="text-red-400">Comm Cost</span> = 2 × distance ÷ c ≈ {yearsLabel(comm)}</div>
          <div><span className="text-amber-400">Earth Wait</span> = Earth Compute + Comm Cost ≈ {yearsLabel(wait)}</div>
          <div><span className={saves ? 'text-green-400' : 'text-red-400'}>Net Gain</span> = task − Earth Wait = {yearsLabel(taskSeconds)} − {yearsLabel(wait)} ≈ {yearsLabel(net)}</div>
          <div className="text-gray-500">Breakeven = Comm Cost ÷ (1 − f_earth/f_server) ≈ {be == null ? 'none' : yearsLabel(be)}</div>
        </div>
      )}
    </div>
  )
}

// Thin one-line legend across the bottom; each item's full description is on hover.
function MapLegend() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="text-[11px] text-gray-500 uppercase tracking-wider mr-1">Map Key</span>
      {LEGEND_ITEMS.map(item => (
        <span key={item.label} className="flex items-center gap-1.5" title={item.desc}>
          <Swatch type={item.swatch} color={item.color} />
          <span className="text-[11px] text-gray-300">{item.label}</span>
        </span>
      ))}
    </div>
  )
}

// Inline breakeven readout (sits in the Task Workload top bar).
function BreakevenLine({ breakeven, taskSeconds }) {
  if (breakeven === undefined) return null // no server placed yet
  const title = "Smallest task whose time-dilation savings cover the round-trip light delay at this location. Tasks larger than this net a gain; smaller ones net a loss."
  if (breakeven === null) {
    return (
      <span className="text-[11px] italic text-gray-500 whitespace-nowrap" title={title}>
        Breakeven: <span className="text-red-400 not-italic">none</span>
      </span>
    )
  }
  const winning = taskSeconds >= breakeven
  return (
    <span className="text-[11px] italic text-gray-500 whitespace-nowrap" title={title}>
      Breakeven:{' '}
      <span className={`not-italic font-mono ${winning ? 'text-green-400' : 'text-red-400'}`}>
        {yearsLabel(breakeven)}
      </span>
    </span>
  )
}

// Segmented control that switches the dashboard between the configured map
// scales (cyan = active). Data-driven over SCALE_UI, so it renders one button
// per registered scale.
function ScaleToggle({ scale, onScaleChange }) {
  return (
    <div className="inline-flex rounded-lg border border-gray-700 overflow-hidden">
      {Object.entries(SCALE_UI).map(([key, cfg]) => {
        const active = scale === key
        return (
          <button
            key={key}
            onClick={() => onScaleChange(key)}
            className={`px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
              active ? 'bg-cyan-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'
            }`}
          >
            {cfg.toggleLabel}
          </button>
        )
      })}
    </div>
  )
}

function TopBar({ taskSeconds, onTaskSecondsChange, breakeven, serverPosition, onPlaceServer, deployCoords, onDeployCoordsChange, scale, onScaleChange }) {
  // The field is entered in YEARS (decimals allowed). Local text holds the raw
  // keystrokes while editing so decimals can be typed without the value being
  // reformatted mid-entry; it's re-grouped with commas on blur. taskSeconds is
  // only ever changed by this field, so there's no external value to sync back.
  const [text, setText] = useState(() => yearsInput(taskSeconds))
  const ui = SCALE_UI[scale]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-2 relative z-40">
      <ScaleToggle scale={scale} onScaleChange={onScaleChange} />
      <span className="h-5 w-px bg-gray-700 hidden sm:block" />
      <label
        className="text-xs text-gray-400 uppercase tracking-wider whitespace-nowrap"
        title="Workload size: compute-years the job needs, measured on the running machine's own clock."
      >
        Task Workload Size (yrs)
      </label>
      <input
        type="text"
        inputMode="decimal"
        value={text}
        onChange={e => {
          const raw = e.target.value
          setText(raw) // keep raw keystrokes so decimals (e.g. "0.5") are typeable
          const y = parseYearsInput(raw)
          if (y !== null) onTaskSecondsChange(Math.round(y * 31536000))
        }}
        onBlur={() => setText(yearsInput(taskSeconds))} // re-group with commas when done
        className="w-32 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-base font-mono text-gray-100 focus:border-cyan-500 focus:outline-none"
      />
      <span className="text-[11px] font-mono text-gray-300 whitespace-nowrap">{daysLabel(taskSeconds)}</span>
      <BreakevenLine breakeven={breakeven} taskSeconds={taskSeconds} />
      <span className="h-5 w-px bg-gray-700 hidden sm:block" />
      <Popover label="Deploy Cosmic Server">
        {close => <ServerPlacer onPlaceServer={onPlaceServer} onDone={close}
          coords={deployCoords} onCoordsChange={onDeployCoordsChange} unit={ui.unit} />}
      </Popover>
      <Popover label="Find a Spot">
        {close => <VoidFinder taskSeconds={taskSeconds} onPlaceServer={onPlaceServer} onDone={close} scale={scale} />}
      </Popover>
      <span className="text-[11px] font-mono text-gray-400 sm:ml-auto whitespace-nowrap" title={`Current Cosmic Server coordinates (${ui.unit}).`}>
        <span className="text-gray-500">Server: </span>
        {serverPosition
          ? `(${serverPosition.x.toFixed(1)}, ${serverPosition.y.toFixed(1)}, ${serverPosition.z.toFixed(1)}) ${ui.unit}`
          : 'not placed'}
      </span>
    </div>
  )
}

// Default deploy coords: a modest 10 units out in the active scale (10 pc solar,
// 10 Mpc cosmic — the distance field is read in that scale's unit). Long/lat 0.
const defaultDeployCoords = () => ({ distance: 10, longitude: 0, latitude: 0 })

export default function FarFutureView({ taskSeconds, onTaskSecondsChange }) {
  const [scale, setScale] = useState('solar')
  const [stars, setStars] = useState([])
  const [serverPosition, setServerPosition] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  // Galactic coords shown in the Deploy form; kept here so a map-click placement
  // updates them and they survive the popover closing/reopening.
  const [deployCoords, setDeployCoords] = useState(() => defaultDeployCoords())

  // Fetch the catalog for the active scale. Switching scales also clears the
  // placed server / metrics and resets the deploy form to that scale's default,
  // since coords/metrics from one catalog don't carry over to the other.
  useEffect(() => {
    setLoading(true)
    setServerPosition(null)
    setMetrics(null)
    setDeployCoords(defaultDeployCoords())
    // Deep Field has no catalog endpoint — its galaxies stream as LOD tiles
    // (2E.2). Skip the /api fetch and start with an empty field; markers, grid
    // and the deploy form still work in the interim.
    if (SCALE_UI[scale].endpoint == null) {
      setStars([])
      setLoading(false)
      return
    }
    fetch(SCALE_UI[scale].endpoint)
      .then(res => res.json())
      .then(data => { setStars(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [scale])

  const placeServer = useCallback(async (coords) => {
    setServerPosition(coords)
    // Sync the Deploy form to wherever the server landed (map click, finder, etc.).
    setDeployCoords(cartesianToGalactic(coords.x, coords.y, coords.z))
    try {
      const res = await fetch('/api/physics/efficiency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          x: coords.x,
          y: coords.y,
          z: coords.z,
          task_seconds: taskSeconds,
          scale,
        }),
      })
      setMetrics(await res.json())
    } catch {
      setMetrics(null)
    }
  }, [taskSeconds, scale])

  // Re-run the efficiency calc when the task size changes. Deps intentionally
  // omit placeServer/serverPosition: placeServer is already useCallback'd on
  // taskSeconds (so the closure is current), and serverPosition changes post
  // via placeServer directly — listing them here would double-post.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (serverPosition) placeServer(serverPosition)
  }, [taskSeconds])

  const ui = SCALE_UI[scale]

  if (loading) {
    return <p className="text-gray-500 text-center py-20 font-mono">Loading {ui.objectNoun} field...</p>
  }

  return (
    <div className="space-y-4">
      <TopBar taskSeconds={taskSeconds} onTaskSecondsChange={onTaskSecondsChange}
        breakeven={metrics ? metrics.breakeven_task_seconds : undefined}
        serverPosition={serverPosition} onPlaceServer={placeServer}
        deployCoords={deployCoords} onDeployCoordsChange={setDeployCoords}
        scale={scale} onScaleChange={setScale} />
      <GalaxyMap stars={stars} serverPosition={serverPosition} onPlaceServer={placeServer}
        unit={ui.unit} originLabel={ui.originLabel}
        scene={ui.scene} scale={scale} assetBase={ui.assetBase} />
      {metrics && (
        <MetricsDash
          distancePc={serverPosition
            ? Math.sqrt(serverPosition.x ** 2 + serverPosition.y ** 2 + serverPosition.z ** 2)
            : 0}
          unit={ui.unit} originLabel={ui.originLabel}
          clockAdvantage={metrics.clock_advantage}
          earthComputeTime={metrics.earth_compute_time}
          earthWaitTime={metrics.earth_wait_time}
          communicationCost={metrics.latency_seconds}
          netGain={metrics.net_gain}
        />
      )}
      <PlainSummary taskSeconds={taskSeconds} metrics={metrics} />
      <MapLegend />
    </div>
  )
}
