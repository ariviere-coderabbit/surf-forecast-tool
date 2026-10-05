import { useState } from 'react'
import { geocode, saveSession } from '../api/client'
import type { GeoCandidate, Observations, SessionRating, SurfSession } from '../api/types'
import { localInputValue } from '../utils/time'

export const observationFields = [
  ['wave_height_m', 'Wave height (m)', 0, 50],
  ['wave_period_s', 'Wave period (s)', 0.1, 60],
  ['wave_direction_deg', 'Wave direction (° from north)', 0, 359.9],
  ['wind_speed_mps', 'Wind speed (m/s)', 0, 150],
  ['wind_direction_deg', 'Wind direction (° from north)', 0, 359.9],
] as const

interface Props {
  location?: GeoCandidate
  session?: SurfSession
  onSaved: (session: SurfSession) => void
  onCancel: () => void
}

export default function SessionForm({ location: initialLocation, session, onSaved, onCancel }: Props) {
  const [location, setLocation] = useState(session?.location ?? initialLocation)
  const [time, setTime] = useState(localInputValue(session?.session_at ?? new Date().toISOString(), (session?.location ?? initialLocation)?.timezone ?? 'UTC'))
  const [timeEdited, setTimeEdited] = useState(false)
  const [note, setNote] = useState(session?.note ?? '')
  const [rating, setRating] = useState<SessionRating>(session?.rating ?? 'good')
  const [observations, setObservations] = useState<Observations>(session?.observations ?? { tide_stage: 'unknown', tide_movement: 'unknown' })
  const [query, setQuery] = useState('')
  const [candidates, setCandidates] = useState<GeoCandidate[]>([])
  const [searching, setSearching] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function search() {
    setSearching(true)
    setError('')
    try {
      const result = await geocode(query)
      setCandidates(result.candidates)
      if (!result.candidates.length) setError('No locations found.')
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setSearching(false) }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!location) { setError('Choose a location first.'); return }
    if (!note.trim()) { setError('Write a session note.'); return }
    setBusy(true)
    setError('')
    try {
      // Preserve the original instant (including seconds and DST fold) on a note-only edit.
      const unchangedTime = session && time === localInputValue(session.session_at, session.location.timezone)
        && location.timezone === session.location.timezone
      const saved = await saveSession({ location, session_at: unchangedTime ? session.session_at : time, note, rating, observations }, session?.id)
      onSaved(saved)
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  return <form onSubmit={submit} className="journal-form">
    <h3>{session ? 'Edit session' : 'Log a session'}</h3>
    <fieldset disabled={busy}>
      <legend>Session details</legend>
      {location && <p>Location: <strong>{location.name}</strong> · {location.timezone}</p>}
      <details open={!location}>
        <summary>{location ? 'Change location' : 'Choose a location'}</summary>
        <label>Session location search<input value={query} onChange={e => setQuery(e.target.value)} /></label>
        <button type="button" disabled={searching || !query.trim()} onClick={search}>{searching ? 'Finding locations…' : 'Find location'}</button>
        {candidates.map(candidate => <button key={`${candidate.id}-${candidate.latitude}-${candidate.longitude}`} type="button" onClick={() => { setLocation(candidate); setCandidates([]); setError('')
          if (!timeEdited) setTime(localInputValue(session?.session_at ?? new Date().toISOString(), candidate.timezone)) }}>
          {candidate.name}, {candidate.country}
        </button>)}
      </details>
      <label>Session date and time ({location?.timezone ?? 'UTC'})
        <input type="datetime-local" required value={time} onChange={e => { setTime(e.target.value); setTimeEdited(true) }} />
      </label>
      <label>How was the surf?
        <select value={rating} onChange={e => setRating(e.target.value as SessionRating)}>
          {['poor', 'okay', 'good', 'great'].map(value => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}
        </select>
      </label>
      <label>In your own words<textarea required maxLength={10000} rows={4} value={note} onChange={e => setNote(e.target.value)} placeholder="Clean waves, light wind, had a great session…" /></label>
      <details>
        <summary>Observed conditions (optional)</summary>
        <p>What you saw stays separate from the modeled forecast. Directions are where waves or wind came from.</p>
        {observationFields.map(([key, label, min, max]) => <label key={key}>{label}
          <input type="number" step="any" min={min} max={max} value={observations[key] ?? ''} onChange={e => setObservations({ ...observations, [key]: e.target.value === '' ? null : Number(e.target.value) })} />
        </label>)}
        <label>Observed tide stage<select value={observations.tide_stage} onChange={e => setObservations({ ...observations, tide_stage: e.target.value as Observations['tide_stage'] })}>
          {['unknown', 'low', 'mid', 'high'].map(value => <option key={value}>{value}</option>)}
        </select></label>
        <label>Observed tide movement<select value={observations.tide_movement} onChange={e => setObservations({ ...observations, tide_movement: e.target.value as Observations['tide_movement'] })}>
          {['unknown', 'rising', 'falling'].map(value => <option key={value}>{value}</option>)}
        </select></label>
      </details>
      <p>Available modeled conditions will be attached for this hour. Earlier sessions may have no weather data.</p>
      <button type="submit">{busy ? 'Saving…' : 'Save session'}</button> <button type="button" onClick={onCancel}>Cancel</button>
    </fieldset>
    {error && <p role="alert">{error}</p>}
  </form>
}
