import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

export default function LedgerTimeline({ earthTxs, marsTxs, syncOffset }) {
  const data = useMemo(() => {
    const lightDelay = 750
    const correction = lightDelay * syncOffset

    const earthPoints = earthTxs.map((tx, i) => ({
      x: tx.timestamp,
      y: i + 1,
    }))

    const marsPoints = marsTxs.map((tx, i) => ({
      x: tx.timestamp + lightDelay - correction,
      y: i + 1,
    }))

    return {
      datasets: [
        {
          label: 'Earth Ledger',
          data: earthPoints,
          borderColor: '#22c55e',
          backgroundColor: '#22c55e',
          pointRadius: 3,
          tension: 0.1,
        },
        {
          label: 'Mars Ledger (as seen from Earth)',
          data: marsPoints,
          borderColor: '#f97316',
          backgroundColor: '#f97316',
          pointRadius: 3,
          tension: 0.1,
        },
      ],
    }
  }, [earthTxs, marsTxs, syncOffset])

  const options = {
    responsive: true,
    maintainAspectRatio: false,
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
    },
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-[400px]">
      <Line data={data} options={options} />
    </div>
  )
}
