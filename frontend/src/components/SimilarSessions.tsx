import { useEffect, useState } from 'react'
import { fetchSessionMatches } from '../api/client'
import type { ForecastResponse, MatchesResponse, SurfSession } from '../api/types'
import { formatLocal } from '../utils/time'

const fieldLabels: Record<string, string> = {
  wave_height_m: 'Wave height (m)', wave_period_s: 'Wave period (s)',
  wave_direction_deg: 'Wave direction (°)', wind_speed_mps: 'Wind speed (m/s)',
  wind_direction_deg: 'Wind direction (°)', sea_level_m: 'Modeled sea level (m)',
}

export default function SimilarSessions({ forecast, revision, onOpen }: {
  forecast: ForecastResponse; revision: number; onOpen: (session: SurfSession) => void
}) {
  const [hour, setHour] = useState(forecast.hourly.find(h => new Date(h.timestamp).getTime() >= Math.floor(Date.now() / 3600000) * 3600000)?.timestamp ?? forecast.hourly[0]?.timestamp ?? '')
  const [result, setResult] = useState<MatchesResponse | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setResult(null)
    setError('')
    if (hour) fetchSessionMatches(forecast.location, hour).then(data => { if (active) setResult(data) })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : String(e)) })
    return () => { active = false }
  }, [forecast, hour, revision])
  if (!hour) return null
  return <section className="journal-panel" aria-label="Similar sessions">
    <h2>Similar sessions from your journal</h2>
    <label>Compare forecast hour<select value={hour} onChange={e => setHour(e.target.value)}>
      {forecast.hourly.map(h => <option key={h.timestamp} value={h.timestamp}>{formatLocal(h.timestamp, forecast.location.timezone)}</option>)}
    </select></label>
    {error && <p role="alert">Could not load similar sessions: {error}</p>}
    {!result && !error && <p>Finding similar sessions…</p>}
    {result && result.status !== 'available' && <p>Not enough forecast data for this hour to compare your sessions.</p>}
    {result?.status === 'available' && !result.matches.length && <p>No sufficiently similar sessions yet. Log a session to build your journal.</p>}
    {result?.matches.map(match => <article key={match.session.id}>
      <h3>{match.session.rating.toUpperCase()} · {formatLocal(match.session.session_at, match.session.location.timezone)}</h3>
      <p className="session-note">{match.session.note}</p>
      <p>Observed tide: {match.session.observations.tide_stage}, {match.session.observations.tide_movement}. Tide stage is context only.</p>
      <div className="table-scroll"><table>
        <caption>Conditions within the comparison tolerances</caption>
        <thead><tr><th>Condition</th><th>Past session</th><th>Forecast</th><th>Difference</th></tr></thead>
        <tbody>{match.comparisons.map(c => <tr key={c.field}>
          <th>{fieldLabels[c.field] ?? c.field}</th><td>{c.session_value.toFixed(1)} ({c.source})</td><td>{c.forecast_value.toFixed(1)}</td><td>{c.difference.toFixed(1)}</td>
        </tr>)}</tbody>
      </table></div>
      <button onClick={() => onOpen(match.session)}>View session</button>
    </article>)}
    <p>Past experiences provide context. Similar conditions do not guarantee the same outcome or change the forecast score.</p>
  </section>
}
