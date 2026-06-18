import { useState } from 'react'

// A control-panel card with a clickable header that collapses its body.
export default function CollapsibleCard({ title, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <button
        onClick={() => setOpen(o => !o)}
        title={open ? 'Collapse' : 'Expand'}
        className="w-full flex items-center justify-between text-sm font-semibold text-cyan-400 uppercase tracking-wider"
      >
        <span>{title}</span>
        <span className="text-gray-500 text-xs">{open ? '▾' : '▸'}</span>
      </button>
      {open && <div className="space-y-4 mt-4">{children}</div>}
    </div>
  )
}
