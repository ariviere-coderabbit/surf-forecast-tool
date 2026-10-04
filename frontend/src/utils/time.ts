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
