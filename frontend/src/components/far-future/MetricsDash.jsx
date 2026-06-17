import { useState, useEffect, useRef } from 'react'
import { commaInt, commaFixed, humanDuration } from '../../utils/format'

function useAnimatedValue(target, duration = 400) {
  const [display, setDisplay] = useState(target)
  const prev = useRef(target)
  const frame = useRef(null)

  useEffect(() => {
    const from = prev.current
    const diff = target - from
    if (Math.abs(diff) < 0.001) { setDisplay(target); prev.current = target; return }

    const start = performance.now()
    const animate = (now) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
      setDisplay(from + diff * eased)
      if (t < 1) { frame.current = requestAnimationFrame(animate) }
      else { prev.current = target }
    }
    frame.current = requestAnimationFrame(animate)
    return () => { if (frame.current) cancelAnimationFrame(frame.current) }
  }, [target, duration])

  return display
}

function MetricCard({ label, value, color, tooltip, arrow, sub, desc }) {
  return (
    <div
      className={`bg-gray-900 border border-gray-800 rounded-xl p-4 hover:shadow-lg transition-shadow ${color}`}
      title={tooltip}
    >
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <div className="flex items-center gap-2">
        <p className="text-2xl font-mono font-bold">{value}</p>
        {arrow && <span className="text-lg">{arrow}</span>}
      </div>
      {sub && <div className="text-[11px] font-mono text-gray-500 mt-1 leading-tight">{sub}</div>}
      {desc && <p className="text-[11px] italic text-gray-500 mt-1 leading-tight">{desc}</p>}
    </div>
  )
}

const LY_PER_PC = 3.26156
const MILES_PER_PC = 1.917e13

const MILE_SCALES = [
  { v: 1e18, w: 'quintillion' },
  { v: 1e15, w: 'quadrillion' },
  { v: 1e12, w: 'trillion' },
  { v: 1e9, w: 'billion' },
  { v: 1e6, w: 'million' },
]

function milesInWords(miles) {
  for (const s of MILE_SCALES) {
    if (miles >= s.v) return `${(miles / s.v).toFixed(1)} ${s.w} miles`
  }
  return `${Math.round(miles).toLocaleString()} miles`
}

function DistanceSub({ pc }) {
  const ly = pc * LY_PER_PC
  const miles = pc * MILES_PER_PC
  const lyStr = ly < 10000 ? ly.toFixed(2) : ly.toExponential(2)
  return (
    <>
      <span className="block">{lyStr} ly · {miles.toExponential(2)} mi</span>
      <span className="block text-gray-600">≈ {milesInWords(miles)}</span>
    </>
  )
}

export default function MetricsDash({ distancePc, clockAdvantage, earthComputeTime, earthWaitTime, communicationCost, netGain }) {
  const animDistance = useAnimatedValue(distancePc ?? 0)
  const animAdvantage = useAnimatedValue(clockAdvantage ?? 1)
  const animCompute = useAnimatedValue(earthComputeTime)
  const animWait = useAnimatedValue(earthWaitTime)
  const animComm = useAnimatedValue(communicationCost ?? 0)
  const animGain = useAnimatedValue(netGain)

  const prevGain = useRef(netGain)
  const improving = netGain > prevGain.current
  useEffect(() => { prevGain.current = netGain }, [netGain])

  if (earthComputeTime == null) return null

  const advantageGood = animAdvantage >= 1

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <MetricCard
        label="Distance from Earth"
        value={`${animDistance.toFixed(2)} pc`}
        sub={<DistanceSub pc={animDistance} />}
        color="text-violet-300 hover:shadow-violet-500/10"
        tooltip="Straight-line distance from Earth to the void server. Shown in parsecs, light-years, and miles (1 pc ≈ 3.26 ly ≈ 1.92×10¹³ mi). This sets the round-trip communication latency."
        desc="Straight-line Earth↔server distance; sets the round-trip latency."
      />
      <MetricCard
        label="Server Clock Advantage"
        value={`${animAdvantage.toFixed(3)}× Earth`}
        sub={advantageGood ? 'server clock runs faster' : 'server clock runs slower'}
        color={advantageGood ? 'text-cyan-400 hover:shadow-cyan-500/10' : 'text-red-400 hover:shadow-red-500/10'}
        tooltip="How fast the server's clock ticks relative to Earth's, based on the local gravitational potential from nearby catalog stars. >1 means the server sits in weaker gravity (a void) and runs faster — the time advantage. <1 means it's in a denser region than Earth and runs slower."
        desc="How fast the server's clock ticks relative to Earth's, derived from local gravity; >1 (green) = void advantage, <1 (red) = denser region than Earth."
      />
      <MetricCard
        label="Earth Compute Time"
        value={`${commaInt(animCompute)} s`}
        sub={humanDuration(animCompute)}
        color="text-cyan-400 hover:shadow-cyan-500/10"
        tooltip="How long Earth's clock measures while the void server completes the task. Because the server's clock runs faster (weaker gravity), it finishes the work in less Earth time than running locally would take."
        desc="How much Earth time passes while the server completes the task."
      />
      <MetricCard
        label="Earth Wait Time"
        value={`${commaInt(animWait)} s`}
        sub={`${humanDuration(animWait)} · +${commaInt(animComm)} s light delay`}
        color="text-amber-400 hover:shadow-amber-500/10"
        tooltip="Total time an Earth observer waits: the compute time plus round-trip light-speed communication latency to the void server and back."
        desc="Compute time + round-trip light delay."
      />
      <MetricCard
        label="Communication Cost"
        value={`${commaInt(animComm)} s`}
        sub={humanDuration(animComm)}
        color="text-amber-400 hover:shadow-amber-500/10"
        tooltip="Round-trip light-speed delay between Earth and the server. This is the fixed time cost that the dilation advantage must overcome."
        desc="Round-trip light-speed delay to the server and back (seconds)."
      />
      <MetricCard
        label={animGain >= 0 ? 'Net Gain' : 'Net Loss'}
        value={`${commaFixed(animGain, 2)} s`}
        color={animGain >= 0 ? 'text-green-400 hover:shadow-green-500/10' : 'text-red-400 hover:shadow-red-500/10'}
        tooltip="Difference between running the task locally on Earth vs. offloading to the void server. Positive = the void server saves time overall. Negative = light-speed latency outweighs the dilation benefit."
        arrow={improving ? '▲' : '▼'}
        desc="Whether the dilation benefit outweighs the communication cost (seconds saved vs. running on Earth)."
      />
    </div>
  )
}
