import { useState, useCallback } from 'react'

export default function useSimulation() {
  const [mode, setMode] = useState('far-future')
  const [taskSeconds, setTaskSeconds] = useState(3600)

  const reset = useCallback(() => {
    setMode('far-future')
    setTaskSeconds(3600)
  }, [])

  return { mode, setMode, taskSeconds, setTaskSeconds, reset }
}
