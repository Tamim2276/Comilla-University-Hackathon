// Numbers and dates in Bangla digits for the screens (e.g. 1234 -> ১,২৩৪).

const number = new Intl.NumberFormat('bn-BD')
const oneDecimal = new Intl.NumberFormat('bn-BD', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const dateTime = new Intl.DateTimeFormat('bn-BD', { dateStyle: 'medium', timeStyle: 'short' })
const time = new Intl.DateTimeFormat('bn-BD', { timeStyle: 'medium' })

export const bnNumber = (n: number): string => number.format(n)

export const bnPercent = (n: number): string => `${oneDecimal.format(n)}%`

/** 3210 ms -> "৩.২" (seconds, one decimal). */
export const bnSeconds = (ms: number): string => oneDecimal.format(ms / 1000)

export function bnDateTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : dateTime.format(d)
}

export const bnTime = (d: Date): string => time.format(d)
