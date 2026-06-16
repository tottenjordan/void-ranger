import { useState, useMemo } from 'react'
import LedgerTimeline from './LedgerTimeline'
import DriftCounter from './DriftCounter'
import SyncSlider from './SyncSlider'
import ledgerData from '../../data/near-future-ledger.json'

export default function NearFutureView() {
  const [syncOffset, setSyncOffset] = useState(0)

  const earthTxs = useMemo(
    () => ledgerData.transactions.filter(t => t.origin === 'earth'),
    [],
  )
  const marsTxs = useMemo(
    () => ledgerData.transactions.filter(t => t.origin === 'mars'),
    [],
  )

  const { driftCount, conflicts } = useMemo(() => {
    const lightDelay = ledgerData.lightDelaySeconds
    const correction = lightDelay * syncOffset

    const allSorted = ledgerData.transactions
      .map(tx => ({
        ...tx,
        perceived: tx.origin === 'mars'
          ? tx.timestamp + lightDelay - correction
          : tx.timestamp,
      }))
      .sort((a, b) => a.perceived - b.perceived)

    let errors = 0
    const conflicts = []
    for (let i = 1; i < allSorted.length; i++) {
      if (allSorted[i].id < allSorted[i - 1].id) {
        errors++
        conflicts.push({
          x: allSorted[i].perceived,
          laterId: allSorted[i - 1].id,
          earlierId: allSorted[i].id,
        })
      }
    }
    return { driftCount: errors, conflicts }
  }, [syncOffset])

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <LedgerTimeline earthTxs={earthTxs} marsTxs={marsTxs} syncOffset={syncOffset} conflicts={conflicts} />
        </div>
        <div className="space-y-6">
          <DriftCounter driftCount={driftCount} totalTransactions={ledgerData.transactions.length} />
          <SyncSlider value={syncOffset} onChange={setSyncOffset} />
        </div>
      </div>
    </div>
  )
}
