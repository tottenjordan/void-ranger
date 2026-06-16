const descriptions = [
  { max: 0, text: 'No light-delay compensation — Mars transactions arrive 750s late' },
  { max: 0.25, text: 'Minimal compensation — ~563s residual delay' },
  { max: 0.50, text: 'Partial compensation — ~375s residual delay' },
  { max: 0.75, text: 'Strong compensation — ~188s residual delay' },
  { max: 1.0, text: 'Full compensation — timestamps pre-adjusted for light delay' },
]

function getDescription(value) {
  for (const d of descriptions) {
    if (value <= d.max) return d.text
  }
  return descriptions[descriptions.length - 1].text
}

export default function SyncSlider({ value, onChange }) {
  const pct = Math.round(value * 100)
  const ticks = [0, 25, 50, 75, 100]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-gray-500 uppercase tracking-wider">Relativistic Sync Protocol</p>
        <span className="text-sm font-mono text-cyan-400">{pct}%</span>
      </div>
      <div className="relative pt-1 pb-4">
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-gray-600 to-cyan-500 rounded-full transition-all duration-150"
            style={{ width: `${pct}%` }}
          />
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={value}
          onChange={e => onChange(Number(e.target.value))}
          className="absolute inset-0 w-full h-2 opacity-0 cursor-pointer"
          style={{ top: '4px' }}
        />
        <div className="flex justify-between mt-1.5">
          {ticks.map(t => (
            <div key={t} className="flex flex-col items-center">
              <div className="w-px h-1.5 bg-gray-600" />
              <span className="text-[9px] text-gray-600 mt-0.5">{t}%</span>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-1 leading-relaxed">{getDescription(value)}</p>
    </div>
  )
}
