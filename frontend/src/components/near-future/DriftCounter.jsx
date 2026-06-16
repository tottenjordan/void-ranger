export default function DriftCounter({ driftCount, totalTransactions }) {
  const severity = driftCount === 0 ? 'green' : driftCount < 5 ? 'amber' : 'red'
  const colors = {
    green: 'border-green-800 text-green-400',
    amber: 'border-amber-800 text-amber-400',
    red: 'border-red-800 text-red-400 animate-pulse',
  }

  return (
    <div className={`bg-gray-900 border ${colors[severity]} rounded-xl p-4`}>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Data Drift Errors</p>
      <p className="text-3xl font-mono font-bold">{driftCount}</p>
      <p className="text-xs text-gray-500 mt-1">{totalTransactions} transactions processed</p>
    </div>
  )
}
