import { useState, useRef, useEffect } from 'react'

// A top-bar toggle whose panel floats over the content below (absolute, so it
// doesn't push the layout down). Closes on outside-click. `children` may be a
// render function `(close) => ...` so the content can dismiss the panel itself.
export default function Popover({ label, width = 'w-80', children }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const close = () => setOpen(false)

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-1 text-xs font-semibold uppercase tracking-wider px-3 py-1.5 rounded-lg border transition-colors ${
          open
            ? 'bg-gray-800 border-cyan-600 text-cyan-300'
            : 'bg-gray-800/60 border-gray-700 text-gray-300 hover:border-gray-600'
        }`}
      >
        {label} <span className="text-gray-500">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className={`absolute left-0 top-full mt-2 z-50 ${width} bg-gray-900 border border-gray-700 rounded-xl p-4 shadow-2xl shadow-black/60`}>
          {typeof children === 'function' ? children(close) : children}
        </div>
      )}
    </div>
  )
}
