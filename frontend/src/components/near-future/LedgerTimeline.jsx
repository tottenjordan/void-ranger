import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const LIGHT_DELAY = 750

const lightDelayZonePlugin = {
  id: 'lightDelayZone',
  beforeDraw(chart) {
    const syncOffset = chart.options.plugins.lightDelayZone?.syncOffset ?? 0
    const zoneEnd = LIGHT_DELAY * (1 - syncOffset)
    if (zoneEnd <= 0) return

    const { ctx, chartArea, scales } = chart
    const xStart = scales.x.getPixelForValue(0)
    const xEnd = scales.x.getPixelForValue(zoneEnd)
    const clampedEnd = Math.min(xEnd, chartArea.right)

    ctx.save()
    ctx.fillStyle = 'rgba(249, 115, 22, 0.06)'
    ctx.fillRect(xStart, chartArea.top, clampedEnd - xStart, chartArea.bottom - chartArea.top)

    ctx.setLineDash([4, 4])
    ctx.strokeStyle = 'rgba(249, 115, 22, 0.3)'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(clampedEnd, chartArea.top)
    ctx.lineTo(clampedEnd, chartArea.bottom)
    ctx.stroke()

    ctx.setLineDash([])
    ctx.fillStyle = 'rgba(249, 115, 22, 0.5)'
    ctx.font = '10px ui-monospace, monospace'
    ctx.fillText('Light-delay window', xStart + 6, chartArea.top + 14)
    ctx.restore()
  },
}

const conflictMarkersPlugin = {
  id: 'conflictMarkers',
  afterDraw(chart) {
    const conflicts = chart.options.plugins.conflictMarkers?.conflicts
    if (!conflicts?.length) return

    const { ctx, chartArea, scales } = chart
    ctx.save()

    conflicts.forEach(c => {
      const px = scales.x.getPixelForValue(c.x)
      if (px < chartArea.left || px > chartArea.right) return

      ctx.fillStyle = 'rgba(239, 68, 68, 0.15)'
      ctx.fillRect(px - 2, chartArea.top, 4, chartArea.bottom - chartArea.top)

      ctx.fillStyle = 'rgba(239, 68, 68, 0.8)'
      ctx.beginPath()
      ctx.arc(px, chartArea.top + 8, 3, 0, Math.PI * 2)
      ctx.fill()
    })

    ctx.restore()
  },
}

ChartJS.register(lightDelayZonePlugin, conflictMarkersPlugin)

export default function LedgerTimeline({ earthTxs, marsTxs, syncOffset, conflicts = [] }) {
  const data = useMemo(() => {
    const correction = LIGHT_DELAY * syncOffset

    const earthPoints = earthTxs.map((tx, i) => ({
      x: tx.timestamp,
      y: i + 1,
    }))

    const marsPoints = marsTxs.map((tx, i) => ({
      x: tx.timestamp + LIGHT_DELAY - correction,
      y: i + 1,
    }))

    return {
      datasets: [
        {
          label: 'Earth Ledger',
          data: earthPoints,
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34, 197, 94, 0.08)',
          pointBackgroundColor: '#22c55e',
          pointRadius: 4,
          pointHoverRadius: 7,
          pointHoverBorderWidth: 2,
          pointHoverBorderColor: '#fff',
          tension: 0.1,
          fill: 'origin',
        },
        {
          label: 'Mars Ledger (as seen from Earth)',
          data: marsPoints,
          borderColor: '#f97316',
          backgroundColor: 'rgba(249, 115, 22, 0.08)',
          pointBackgroundColor: '#f97316',
          pointRadius: 4,
          pointHoverRadius: 7,
          pointHoverBorderWidth: 2,
          pointHoverBorderColor: '#fff',
          tension: 0.1,
          fill: 'origin',
        },
      ],
    }
  }, [earthTxs, marsTxs, syncOffset])

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 600,
      easing: 'easeInOutQuart',
    },
    interaction: {
      mode: 'index',
      intersect: false,
    },
    scales: {
      x: {
        type: 'linear',
        title: { display: true, text: 'Time (s)', color: '#9ca3af' },
        ticks: { color: '#6b7280' },
        grid: { color: '#1f2937' },
      },
      y: {
        title: { display: true, text: 'Transaction #', color: '#9ca3af' },
        ticks: { color: '#6b7280' },
        grid: { color: '#1f2937' },
      },
    },
    plugins: {
      legend: { labels: { color: '#d1d5db' } },
      tooltip: {
        backgroundColor: '#1f2937',
        borderColor: '#374151',
        borderWidth: 1,
        titleColor: '#e5e7eb',
        bodyColor: '#d1d5db',
      },
      lightDelayZone: { syncOffset },
      conflictMarkers: { conflicts },
    },
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-[400px]">
      <Line data={data} options={options} />
    </div>
  )
}
