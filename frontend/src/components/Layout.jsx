import ModeToggle from './ModeToggle'

export default function Layout({ mode, onModeChange, children }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-wide text-cyan-400">ChronoCloud</h1>
        <ModeToggle mode={mode} onChange={onModeChange} />
      </header>
      <main className="p-6">
        {children}
      </main>
    </div>
  )
}
