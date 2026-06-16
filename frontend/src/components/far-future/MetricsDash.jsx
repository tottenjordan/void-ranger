function formatTime(seconds) {
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(2)} min`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(2)} hr`
  if (seconds < 31536000) return `${(seconds / 86400).toFixed(2)} days`
  return `${(seconds / 31536000).toFixed(2)} yr`
}

function MetricCard({ label, value, color, tooltip }) {
  return (
    <div
      className={`bg-gray-900 border border-gray-800 rounded-xl p-4 hover:shadow-lg transition-shadow ${color}`}
      title={tooltip}
    >
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-mono font-bold">{value}</p>
    </div>
  )
}

export default function MetricsDash({ localTime, earthWaitTime, netGain }) {
  if (localTime == null) return null

  return (
    <div className="grid grid-cols-3 gap-4">
      <MetricCard
        label="Local Server Compute"
        value={formatTime(localTime)}
        color="text-cyan-400 hover:shadow-cyan-500/10"
        tooltip="Time elapsed on the server's local clock (task duration × dilation factor). Gravitational time dilation causes clocks near massive objects to tick slower."
      />
      <MetricCard
        label="Earth Wait Time"
        value={formatTime(earthWaitTime)}
        color="text-amber-400 hover:shadow-amber-500/10"
        tooltip="Total time an Earth observer waits: the server's local compute time plus round-trip light-speed communication latency."
      />
      <MetricCard
        label={netGain >= 0 ? 'Net Gain' : 'Net Loss'}
        value={formatTime(Math.abs(netGain))}
        color={netGain >= 0 ? 'text-green-400 hover:shadow-green-500/10' : 'text-red-400 hover:shadow-red-500/10'}
        tooltip="Difference between running the task locally on Earth vs. on the remote server. Positive = the server finishes before Earth would. Negative = light-speed latency outweighs the dilation benefit."
      />
    </div>
  )
}
