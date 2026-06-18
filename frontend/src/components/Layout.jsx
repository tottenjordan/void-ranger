export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-xl font-bold tracking-wide text-cyan-400">Void Ranger</h1>
      </header>
      <main className="p-6">
        {children}
      </main>
    </div>
  )
}
