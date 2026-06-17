import { useState, useCallback } from 'react'

export default function useSimulation() {
  const [mode, setMode] = useState('far-future')
  const [taskSeconds, setTaskSeconds] = useState(31536000) // default: 1 year

  const reset = useCallback(() => {
    setMode('far-future')
    setTaskSeconds(31536000)
  }, [])

  return { mode, setMode, taskSeconds, setTaskSeconds, reset }
}
