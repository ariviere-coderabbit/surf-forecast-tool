import { useEffect, useState } from 'react'
import { deleteSession, listSessions } from '../api/client'
import type { ForecastResponse, GeoCandidate, SurfSession } from '../api/types'
import { formatLocal } from '../utils/time'
import SessionForm, { observationFields } from './SessionForm'
import SimilarSessions from './SimilarSessions'
import './journal.css'

export default function Journal({ location, forecast }: { location?: GeoCandidate; forecast?: ForecastResponse }) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<SurfSession | 'new' | null>(null)
  const [sessions, setSessions] = useState<SurfSession[]>([])
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [focused, setFocused] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let active = true
    setLoading(true)
    setError('')
    listSessions().then(data => { if (active) setSessions(data) })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : String(e)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [open, revision])

  useEffect(() => {
    if (focused && !loading) document.getElementById(`session-${focused}`)?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  }, [focused, loading, sessions])

  function saved(session: SurfSession) {
    setEditing(null)
    setOpen(true)
    setFocused(session.id)
    setRevision(r => r + 1)
    setNotice(session.snapshot ? 'Session saved with modeled conditions.' : 'Session saved. Modeled conditions were unavailable for this time; your observations are preserved.')
  }

  async function remove(id: string) {
    setBusy(true)
    setError('')
    try {
      await deleteSession(id)
      setDeleting(null)
      setRevision(r => r + 1)
      setNotice('Session deleted.')
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  return <>
    <section className="journal-panel" aria-label="Personal surf journal">
      <h2>Your surf journal</h2>
      <p>Remember what worked, in your own words.</p>
      <button onClick={() => { setEditing('new'); setNotice('') }}>Log a session</button>{' '}
      <button onClick={() => setOpen(!open)} aria-expanded={open}>{open ? 'Hide journal' : 'Journal'}</button>
      {notice && <p role="status">{notice}</p>}
      {editing && <SessionForm key={editing === 'new' ? 'new' : editing.id} location={location}
        session={editing === 'new' ? undefined : editing} onSaved={saved} onCancel={() => setEditing(null)} />}
      {open && <div>
        <h3>Saved sessions</h3>
        {loading && <p>Loading journal…</p>}
        {error && <p role="alert">{error} <button onClick={() => setRevision(r => r + 1)}>Retry</button></p>}
        {!loading && !error && !sessions.length && <p>No sessions yet.</p>}
        {sessions.map(session => <article key={session.id} id={`session-${session.id}`} tabIndex={-1} className={focused === session.id ? 'selected-session' : ''}>
          <h3>{session.location.name} · {session.rating.toUpperCase()}</h3>
          <p>{formatLocal(session.session_at, session.location.timezone)} · {session.location.timezone}</p>
          <p className="session-note">{session.note}</p>
          <details><summary>Saved conditions and observations</summary>
            <h4>Your observations</h4>
            <ul>{observationFields.filter(([key]) => session.observations[key] != null).map(([key, label]) => <li key={key}>{label}: {session.observations[key]}</li>)}</ul>
            <p>Tide: {session.observations.tide_stage}, {session.observations.tide_movement}</p>
            {session.snapshot ? <>
              <h4>Modeled conditions</h4>
              <p>Hour: {formatLocal(session.snapshot.conditions.timestamp, session.location.timezone)}</p>
              <ul>{observationFields.map(([key, label]) => <li key={key}>{label}: {session.snapshot?.conditions[key] ?? 'Unavailable'}</li>)}</ul>
              <p>Modeled sea level: {session.snapshot.conditions.sea_level_m ?? 'Unavailable'} m. This is not a tide prediction.</p>
              <p>Captured {formatLocal(session.snapshot.captured_at, session.location.timezone)}</p>
              <p>Sources: {session.snapshot.providers.map(p => `${p.provider} / ${p.model} (${p.status})`).join(', ') || 'No provider details available'}</p>
              {session.snapshot.notices.map((notice, i) => <p key={i}>{notice}</p>)}
            </> : <p>Modeled conditions unavailable for this session. Your observations are preserved.</p>}
          </details>
          <button onClick={() => { setEditing(session); setNotice('') }}>Edit session</button>{' '}
          <button onClick={() => setDeleting(session.id)}>Delete session</button>
          {deleting === session.id && <div role="group" aria-label="Confirm deletion">
            <p>Delete this session and remove it from future comparisons?</p>
            <button disabled={busy} onClick={() => remove(session.id)}>{busy ? 'Deleting…' : 'Confirm delete'}</button>{' '}
            <button disabled={busy} onClick={() => setDeleting(null)}>Keep session</button>
          </div>}
        </article>)}
      </div>}
    </section>
    {forecast && <SimilarSessions key={`${forecast.location.latitude},${forecast.location.longitude},${forecast.generated_at}`} forecast={forecast} revision={revision}
      onOpen={session => { setOpen(true); setFocused(session.id) }} />}
  </>
}
