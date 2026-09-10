export function formatBytes(bytes: number): string {
  if (!bytes) return '0 KB'
  const units = ['B', 'KB', 'MB', 'GB']
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** exponent
  const decimals = value >= 100 || exponent === 0 ? 0 : 1
  return `${value.toFixed(decimals)} ${units[exponent]}`
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat(undefined).format(value)
}

/** The backend serialises naive UTC datetimes, so mark them as UTC before parsing. */
function parseTimestamp(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = parseTimestamp(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = parseTimestamp(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return '—'
  const date = parseTimestamp(value)
  if (Number.isNaN(date.getTime())) return '—'

  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return 'just now'

  const table: [Intl.RelativeTimeFormatUnit, number][] = [
    ['minute', 60],
    ['hour', 3600],
    ['day', 86400],
    ['month', 2592000],
    ['year', 31536000],
  ]

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  let unit: Intl.RelativeTimeFormatUnit = 'minute'
  let divisor = 60
  for (const [candidate, candidateDivisor] of table) {
    if (seconds < candidateDivisor * 60 || candidate === 'year') {
      unit = candidate
      divisor = candidateDivisor
      break
    }
  }
  return formatter.format(-Math.round(seconds / divisor), unit)
}

export function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max).trimEnd()}…`
}

/** Collapses page runs like [1,2,3,7] into "1–3, 7". */
export function formatPageRanges(pages: number[]): string {
  if (!pages.length) return ''
  const sorted = [...new Set(pages)].sort((a, b) => a - b)
  const ranges: string[] = []
  let start = sorted[0]
  let previous = sorted[0]

  for (const page of sorted.slice(1)) {
    if (page === previous + 1) {
      previous = page
      continue
    }
    ranges.push(start === previous ? `${start}` : `${start}–${previous}`)
    start = page
    previous = page
  }
  ranges.push(start === previous ? `${start}` : `${start}–${previous}`)
  return ranges.join(', ')
}
