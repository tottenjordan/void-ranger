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

// Format a duration given in SECONDS as hours, e.g. 7200 -> "2 hrs".
// digits === null -> whole hours (comma-grouped); otherwise fixed decimals.
export function hoursLabel(seconds, digits = null) {
  if (seconds == null || !isFinite(seconds)) return '—'
  const h = seconds / 3600
  return digits === null ? `${commaInt(h)} hrs` : `${commaFixed(h, digits)} hrs`
}

// Format a duration given in SECONDS as days, e.g. 172800 -> "2 days".
// digits === null -> whole days (comma-grouped); otherwise fixed decimals.
// This is the secondary "how long is that really" unit beneath the years value.
export function daysLabel(seconds, digits = null) {
  if (seconds == null || !isFinite(seconds)) return '—'
  const d = seconds / 86400
  return digits === null ? `${commaInt(d)} days` : `${commaFixed(d, digits)} days`
}

// Format a duration given in SECONDS as whole years, comma-grouped, e.g.
// "114,155 yrs". The prominent unit on the time widgets (days shown beneath).
export function yearsLabel(seconds) {
  if (seconds == null || !isFinite(seconds)) return '—'
  return `${commaInt(seconds / 31536000)} yrs`
}

// Display value for the editable Task Workload Size field, in YEARS. Comma-groups
// the integer part and keeps up to 4 decimals (trailing zeros trimmed) so small,
// sub-year tasks remain enterable, e.g. 31536000 -> "1", 15768000 -> "0.5".
export function yearsInput(seconds) {
  if (seconds == null || !isFinite(seconds)) return '0'
  const y = Math.round((seconds / 31536000) * 10000) / 10000
  const [intPart, decPart] = String(y).split('.')
  const grouped = Number(intPart).toLocaleString('en-US')
  return decPart ? `${grouped}.${decPart}` : grouped
}

// Parse a user-typed YEARS string (digits, commas, one decimal point) into a
// non-negative float number of years. Returns null when nothing usable typed.
export function parseYearsInput(str) {
  const cleaned = String(str).replace(/[^\d.]/g, '')
  if (cleaned === '' || cleaned === '.') return null
  const n = parseFloat(cleaned)
  return isFinite(n) ? n : null
}

// Plain-language duration that auto-picks a relatable unit (seconds → minutes →
// hours → days → years), comma-grouped, with full unit words. Used for the
// "in plain terms" summary so the magnitudes are easy to relate to.
export function relatableDuration(seconds) {
  if (seconds == null || !isFinite(seconds)) return '—'
  const sign = seconds < 0 ? '-' : ''
  const abs = Math.abs(seconds)
  const fmt = (val, unit) => {
    const n = val >= 100 ? Math.round(val).toLocaleString('en-US') : val.toFixed(1)
    return `${sign}${n} ${unit}`
  }
  if (abs < 60) return fmt(abs, 'seconds')
  if (abs < 3600) return fmt(abs / 60, 'minutes')
  if (abs < 86400) return fmt(abs / 3600, 'hours')
  if (abs < 31536000) return fmt(abs / 86400, 'days')
  return fmt(abs / 31536000, 'years')
}

// Inverse of the backend's galactic→Cartesian conversion: turn a placed (x,y,z)
// in parsecs into galactic { distance, longitude(0–360°), latitude(−90–90°) },
// rounded to 1 decimal — used to sync the Deploy form to a map-click placement.
export function cartesianToGalactic(x, y, z) {
  const d = Math.sqrt(x * x + y * y + z * z)
  if (d === 0) return { distance: 0, longitude: 0, latitude: 0 }
  let l = Math.atan2(y, x) * 180 / Math.PI
  if (l < 0) l += 360
  const b = Math.asin(Math.max(-1, Math.min(1, z / d))) * 180 / Math.PI
  const r = n => Math.round(n * 10) / 10
  return { distance: r(d), longitude: r(l), latitude: r(b) }
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
