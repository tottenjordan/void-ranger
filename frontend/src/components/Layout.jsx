import ModeToggle from './ModeToggle'

export default function Layout({ mode, onModeChange, taskSeconds, onTaskSecondsChange, children }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-wide text-cyan-400">ChronoCloud</h1>
        <ModeToggle mode={mode} onChange={onModeChange} />
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-400">Task (s):</label>
          <input
            type="number"
            min="1"
            value={taskSeconds}
            onChange={e => onTaskSecondsChange(Number(e.target.value))}
            className="w-24 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm font-mono text-gray-100 focus:border-cyan-500 focus:outline-none"
          />
        </div>
      </header>
      <main className="p-6">
        {children}
      </main>
    </div>
  )
}
