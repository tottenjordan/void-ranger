export default function SyncSlider({ value, onChange }) {
  const pct = Math.round(value * 100)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-gray-500 uppercase tracking-wider">Relativistic Sync Protocol</p>
        <span className="text-sm font-mono text-cyan-400">{pct}%</span>
      </div>
      <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full accent-cyan-500"
      />
      <div className="flex justify-between text-xs text-gray-600 mt-1">
        <span>No compensation</span>
        <span>Full compensation</span>
      </div>
    </div>
  )
}
