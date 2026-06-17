// Comma-group an integer number of seconds, e.g. 1234567 -> "1,234,567".
export function commaInt(n) {
  if (n == null || !isFinite(n)) return '—'
  return Math.round(n).toLocaleString('en-US')
}

// Comma-group with fixed decimals, e.g. 12345.6 -> "12,345.60".
export function commaFixed(n, digits = 2) {
  if (n == null || !isFinite(n)) return '—'
  return n.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

// Human-readable duration (kept as a secondary subline), mirrors the prior
// MetricsDash formatTime so we don't lose the at-a-glance scale. Sign-safe
// (negative durations keep their '-') and `digits` controls decimal places.
export function humanDuration(seconds, digits = 2) {
  const sign = seconds < 0 ? '-' : ''
  const abs = Math.abs(seconds)
  if (abs < 60) return `${sign}${abs.toFixed(digits)} s`
  if (abs < 3600) return `${sign}${(abs / 60).toFixed(digits)} min`
  if (abs < 86400) return `${sign}${(abs / 3600).toFixed(digits)} hr`
  if (abs < 31536000) return `${sign}${(abs / 86400).toFixed(digits)} days`
  return `${sign}${(abs / 31536000).toFixed(digits)} yr`
}

// Parse a user-typed string into a non-negative integer number of seconds,
// keeping only digit characters (e.g. "12,345" -> 12345). Returns null when
// nothing usable was typed. Note: only plain digits/commas are supported —
// scientific notation is not (it would be stripped to its digits).
export function parseSecondsInput(str) {
  const digits = String(str).replace(/[^\d]/g, '')
  if (digits === '') return null
  return Number(digits)
}
