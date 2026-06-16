import Layout from './components/Layout'
import NearFutureView from './components/near-future/NearFutureView'
import FarFutureView from './components/far-future/FarFutureView'
import useSimulation from './hooks/useSimulation'

export default function App() {
  const { mode, setMode, taskSeconds, setTaskSeconds } = useSimulation()

  return (
    <Layout
      mode={mode}
      onModeChange={setMode}
      taskSeconds={taskSeconds}
      onTaskSecondsChange={setTaskSeconds}
    >
      {mode === 'near-future' ? <NearFutureView /> : <FarFutureView taskSeconds={taskSeconds} />}
    </Layout>
  )
}
