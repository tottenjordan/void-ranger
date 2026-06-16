export default function DriftCounter({ driftCount, totalTransactions }) {
  const pct = totalTransactions > 0 ? Math.round((driftCount / totalTransactions) * 100) : 0
  const severity = driftCount === 0 ? 'green' : driftCount < 5 ? 'amber' : 'red'

  const colors = {
    green: { border: 'border-green-800', text: 'text-green-400', stroke: '#22c55e', glow: '' },
    amber: { border: 'border-amber-800', text: 'text-amber-400', stroke: '#f59e0b', glow: '' },
    red: { border: 'border-red-800', text: 'text-red-400', stroke: '#ef4444', glow: 'shadow-[0_0_20px_rgba(239,68,68,0.3)]' },
  }
  const c = colors[severity]

  const radius = 36
  const circumference = 2 * Math.PI * radius
  const progress = totalTransactions > 0 ? driftCount / totalTransactions : 0
  const offset = circumference * (1 - progress)

  return (
    <div className={`bg-gray-900 border ${c.border} rounded-xl p-4 ${c.glow} transition-shadow duration-500`}>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Data Drift Errors</p>
      <div className="flex items-center gap-4">
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
            <circle
              cx="40" cy="40" r={radius}
              fill="none"
              stroke="#1f2937"
              strokeWidth="6"
            />
            <circle
              cx="40" cy="40" r={radius}
              fill="none"
              stroke={c.stroke}
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              className="transition-all duration-500 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-lg font-mono font-bold ${c.text}`}>{pct}%</span>
          </div>
        </div>
        <div>
          <p className={`text-3xl font-mono font-bold ${c.text}`}>{driftCount}</p>
          <p className="text-xs text-gray-500 mt-1">{totalTransactions} transactions</p>
        </div>
      </div>
    </div>
  )
}
