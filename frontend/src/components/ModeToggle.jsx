export default function ModeToggle({ mode, onChange }) {
  const modes = [
    { key: 'near-future', label: 'Interplanetary DevOps' },
    { key: 'far-future', label: 'Deep-Space Compute' },
  ]

  return (
    <div className="flex rounded-lg border border-gray-700 overflow-hidden">
      {modes.map(m => (
        <button
          key={m.key}
          onClick={() => onChange(m.key)}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            mode === m.key
              ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500'
              : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}
