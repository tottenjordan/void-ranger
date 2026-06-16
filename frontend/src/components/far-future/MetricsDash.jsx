import { useState, useEffect, useRef } from 'react'

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

function formatTime(seconds) {
  const abs = Math.abs(seconds)
  if (abs < 60) return `${abs.toFixed(2)}s`
  if (abs < 3600) return `${(abs / 60).toFixed(2)} min`
  if (abs < 86400) return `${(abs / 3600).toFixed(2)} hr`
  if (abs < 31536000) return `${(abs / 86400).toFixed(2)} days`
  return `${(abs / 31536000).toFixed(2)} yr`
}

function MetricCard({ label, value, color, tooltip, arrow }) {
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
    </div>
  )
}

export default function MetricsDash({ localTime, earthWaitTime, netGain }) {
  if (localTime == null) return null

  const animLocal = useAnimatedValue(localTime)
  const animEarth = useAnimatedValue(earthWaitTime)
  const animGain = useAnimatedValue(netGain)

  const prevGain = useRef(netGain)
  const improving = netGain > prevGain.current
  useEffect(() => { prevGain.current = netGain }, [netGain])

  return (
    <div className="grid grid-cols-3 gap-4">
      <MetricCard
        label="Local Server Compute"
        value={formatTime(animLocal)}
        color="text-cyan-400 hover:shadow-cyan-500/10"
        tooltip="Time elapsed on the server's local clock (task duration x dilation factor). Gravitational time dilation causes clocks near massive objects to tick slower."
      />
      <MetricCard
        label="Earth Wait Time"
        value={formatTime(animEarth)}
        color="text-amber-400 hover:shadow-amber-500/10"
        tooltip="Total time an Earth observer waits: the server's local compute time plus round-trip light-speed communication latency."
      />
      <MetricCard
        label={animGain >= 0 ? 'Net Gain' : 'Net Loss'}
        value={formatTime(animGain)}
        color={animGain >= 0 ? 'text-green-400 hover:shadow-green-500/10' : 'text-red-400 hover:shadow-red-500/10'}
        tooltip="Difference between running the task locally on Earth vs. on the remote server. Positive = the server finishes before Earth would. Negative = light-speed latency outweighs the dilation benefit."
        arrow={improving ? '▲' : '▼'}
      />
    </div>
  )
}
