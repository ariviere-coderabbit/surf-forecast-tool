/** Format an ISO-8601 UTC timestamp in the given IANA timezone. */
export function formatLocal(isoUtc: string, timezone: string): string {
  try {
    return new Date(isoUtc).toLocaleString('en-US', {
      timeZone: timezone,
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
  } catch {
    return isoUtc
  }
}

/** Format just the time portion (for hourly rows). */
export function formatTime(isoUtc: string, timezone: string): string {
  try {
    return new Date(isoUtc).toLocaleString('en-US', {
      timeZone: timezone,
      weekday: 'short',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
  } catch {
    return isoUtc
  }
}

/** Wall time for datetime-local; conversion to UTC happens on the backend. */
export function localInputValue(isoUtc: string, timezone: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(isoUtc))
  const part = (key: string) => parts.find(p => p.type === key)?.value
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`
}
