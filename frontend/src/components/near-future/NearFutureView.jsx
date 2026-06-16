import { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import LedgerTimeline from './LedgerTimeline'
import DriftCounter from './DriftCounter'
import SyncSlider from './SyncSlider'
import ledgerData from '../../data/near-future-ledger.json'

const LIGHT_DELAY = ledgerData.lightDelaySeconds

function computePerceived(transactions, syncOffset) {
  const correction = LIGHT_DELAY * syncOffset
  return transactions.map(tx => ({
    ...tx,
    perceived: tx.origin === 'mars'
      ? tx.timestamp + LIGHT_DELAY - correction
      : tx.timestamp,
  }))
}

export default function NearFutureView() {
  const [syncOffset, setSyncOffset] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [currentTime, setCurrentTime] = useState(null)
  const frameRef = useRef(null)
  const lastTickRef = useRef(null)

  const earthTxs = useMemo(
    () => ledgerData.transactions.filter(t => t.origin === 'earth'),
    [],
  )
  const marsTxs = useMemo(
    () => ledgerData.transactions.filter(t => t.origin === 'mars'),
    [],
  )

  const perceived = useMemo(
    () => computePerceived(ledgerData.transactions, syncOffset),
    [syncOffset],
  )

  const maxTime = useMemo(() => {
    return Math.max(...perceived.map(t => t.perceived))
  }, [perceived])

  const { driftCount, conflicts, liveDriftCount } = useMemo(() => {
    const sorted = [...perceived].sort((a, b) => a.perceived - b.perceived)

    let errors = 0
    const conflicts = []
    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i].id < sorted[i - 1].id) {
        errors++
        conflicts.push({
          x: sorted[i].perceived,
          laterId: sorted[i - 1].id,
          earlierId: sorted[i].id,
        })
      }
    }

    let liveDrift = errors
    if (currentTime != null) {
      const visible = sorted.filter(t => t.perceived <= currentTime)
      liveDrift = 0
      for (let i = 1; i < visible.length; i++) {
        if (visible[i].id < visible[i - 1].id) liveDrift++
      }
    }

    return { driftCount: errors, conflicts, liveDriftCount: liveDrift }
  }, [perceived, currentTime])

  const tick = useCallback((now) => {
    if (lastTickRef.current == null) lastTickRef.current = now
    const delta = (now - lastTickRef.current) / 1000
    lastTickRef.current = now

    setCurrentTime(prev => {
      const next = (prev ?? 0) + delta * speed * 40
      if (next >= maxTime) {
        setPlaying(false)
        return maxTime
      }
      return next
    })
    frameRef.current = requestAnimationFrame(tick)
  }, [speed, maxTime])

  useEffect(() => {
    if (playing) {
      lastTickRef.current = null
      frameRef.current = requestAnimationFrame(tick)
    } else {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current) }
  }, [playing, tick])

  const handlePlay = () => {
    if (currentTime != null && currentTime >= maxTime) setCurrentTime(0)
    setPlaying(true)
  }

  const handleStop = () => {
    setPlaying(false)
    setCurrentTime(null)
  }

  const displayDrift = currentTime != null ? liveDriftCount : driftCount
  const processedCount = currentTime != null
    ? perceived.filter(t => t.perceived <= currentTime).length
    : ledgerData.transactions.length

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          <LedgerTimeline
            earthTxs={earthTxs}
            marsTxs={marsTxs}
            syncOffset={syncOffset}
            conflicts={conflicts}
            playheadTime={currentTime}
          />
          <div className="flex items-center gap-3">
            {!playing ? (
              <button
                onClick={handlePlay}
                className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {currentTime != null && currentTime < maxTime ? 'Resume' : 'Play'}
              </button>
            ) : (
              <button
                onClick={() => setPlaying(false)}
                className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Pause
              </button>
            )}
            <button
              onClick={handleStop}
              className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg transition-colors"
            >
              Reset
            </button>
            <div className="flex items-center gap-1.5 ml-auto">
              <span className="text-xs text-gray-500">Speed:</span>
              {[1, 2, 5].map(s => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-2 py-0.5 text-xs rounded transition-colors ${
                    speed === s
                      ? 'bg-cyan-500/20 text-cyan-400'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="space-y-6">
          <DriftCounter driftCount={displayDrift} totalTransactions={processedCount} />
          <SyncSlider value={syncOffset} onChange={setSyncOffset} />
        </div>
      </div>
    </div>
  )
}
