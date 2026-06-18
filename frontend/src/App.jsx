import { useState } from 'react'
import Layout from './components/Layout'
import FarFutureView from './components/far-future/FarFutureView'

export default function App() {
  const [taskSeconds, setTaskSeconds] = useState(31536000) // default: 1 year

  return (
    <Layout>
      <FarFutureView taskSeconds={taskSeconds} onTaskSecondsChange={setTaskSeconds} />
    </Layout>
  )
}
