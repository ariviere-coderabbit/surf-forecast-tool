import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api/client'
import Journal from '../components/Journal'
import SessionForm from '../components/SessionForm'
import SimilarSessions from '../components/SimilarSessions'
import { localInputValue } from '../utils/time'
import { forecast, location, session } from './journal-fixtures'

vi.mock('../api/client')

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.listSessions).mockResolvedValue([])
  vi.mocked(api.saveSession).mockResolvedValue(session)
  vi.mocked(api.fetchSessionMatches).mockResolvedValue({ hour: forecast.hourly[0].timestamp, status: 'available', matches: [] })
})

describe('session capture', () => {
  it('saves a past session with original words, rating, and optional observations', async () => {
    render(<Journal location={location} />)
    await userEvent.click(screen.getByRole('button', { name: 'Log a session' }))
    fireEvent.change(screen.getByLabelText(/Session date and time/), { target: { value: '2024-01-15T06:30' } })
    await userEvent.type(screen.getByLabelText('In your own words'), 'Great waves!')
    await userEvent.selectOptions(screen.getByLabelText('How was the surf?'), 'great')
    await userEvent.click(screen.getByText('Observed conditions (optional)'))
    await userEvent.type(screen.getByLabelText('Wind speed (m/s)'), '2.5')
    await userEvent.selectOptions(screen.getByLabelText('Observed tide stage'), 'high')
    await userEvent.click(screen.getByRole('button', { name: 'Save session' }))
    expect(api.saveSession).toHaveBeenCalledWith(expect.objectContaining({
      location, session_at: '2024-01-15T06:30', note: 'Great waves!', rating: 'great',
      observations: expect.objectContaining({ wind_speed_mps: 2.5, tide_stage: 'high' }),
    }), undefined)
    expect(await screen.findByRole('status')).toHaveTextContent('Modeled conditions were unavailable')
    expect(api.listSessions).toHaveBeenCalled()
  })

  it('defaults to the current spot wall time', () => {
    render(<SessionForm location={location} onSaved={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByLabelText(/Session date and time/)).toHaveValue(localInputValue(new Date().toISOString(), location.timezone))
  })

  it('keeps the note and displays a save error without closing the form', async () => {
    vi.mocked(api.saveSession).mockRejectedValue(new Error('Database unavailable'))
    render(<SessionForm location={location} session={session} onSaved={vi.fn()} onCancel={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Save session' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Database unavailable')
    expect(screen.getByLabelText('In your own words')).toHaveValue(session.note)
  })

  it('requires a selected location and allows finding it without a forecast', async () => {
    vi.mocked(api.geocode).mockResolvedValue({ query: 'Jaco', candidates: [location] })
    render(<SessionForm onSaved={vi.fn()} onCancel={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('In your own words'), 'Nice day')
    await userEvent.click(screen.getByRole('button', { name: 'Save session' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Choose a location first')
    await userEvent.type(screen.getByLabelText('Session location search'), 'Jaco')
    await userEvent.click(screen.getByRole('button', { name: 'Find location' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Jacó, Costa Rica' }))
    expect(screen.getByLabelText(/Session date and time/)).toBeInTheDocument()
    expect(api.saveSession).not.toHaveBeenCalled()
  })

  it('rejects whitespace-only notes', async () => {
    render(<SessionForm location={location} onSaved={vi.fn()} onCancel={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('In your own words'), '   ')
    await userEvent.click(screen.getByRole('button', { name: 'Save session' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Write a session note')
    expect(api.saveSession).not.toHaveBeenCalled()
  })
})

describe('journal and analysis', () => {
  it('edits a session while preserving its exact original instant', async () => {
    vi.mocked(api.listSessions).mockResolvedValue([session])
    render(<Journal location={location} />)
    await userEvent.click(screen.getByRole('button', { name: 'Journal' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Edit session' }))
    await userEvent.clear(screen.getByLabelText('In your own words'))
    await userEvent.type(screen.getByLabelText('In your own words'), 'A corrected note')
    await userEvent.click(screen.getByRole('button', { name: 'Save session' }))
    expect(api.saveSession).toHaveBeenCalledWith(expect.objectContaining({ note: 'A corrected note', session_at: session.session_at }), session.id)
  })

  it('confirms deletion and refreshes both journal and comparisons', async () => {
    vi.mocked(api.listSessions).mockResolvedValueOnce([session]).mockResolvedValue([])
    render(<Journal location={location} forecast={forecast} />)
    await userEvent.click(screen.getByRole('button', { name: 'Journal' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Delete session' }))
    expect(api.deleteSession).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))
    await waitFor(() => expect(api.deleteSession).toHaveBeenCalledWith(session.id))
    expect(await screen.findByText('No sessions yet.')).toBeInTheDocument()
    expect(api.fetchSessionMatches).toHaveBeenCalledTimes(2)
  })

  it('shows match evidence and opens the original session', async () => {
    const onOpen = vi.fn()
    vi.mocked(api.fetchSessionMatches).mockResolvedValue({ hour: forecast.hourly[0].timestamp, status: 'available', matches: [{
      session, distance: 0.2, comparisons: [{ field: 'wind_speed_mps', session_value: 2, forecast_value: 3, difference: 1, tolerance: 2, source: 'observed' }],
    }] })
    render(<SimilarSessions forecast={forecast} revision={0} onOpen={onOpen} />)
    expect(await screen.findByText(session.note)).toBeInTheDocument()
    expect(screen.getByText('2.0 (observed)')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'View session' }))
    expect(onOpen).toHaveBeenCalledWith(session)
    await userEvent.selectOptions(screen.getByLabelText('Compare forecast hour'), forecast.hourly[1].timestamp)
    await waitFor(() => expect(api.fetchSessionMatches).toHaveBeenLastCalledWith(location, forecast.hourly[1].timestamp))
  })

  it('handles no matches, incomplete forecast, and list errors', async () => {
    vi.mocked(api.listSessions).mockRejectedValue(new Error('Journal offline'))
    render(<Journal forecast={forecast} />)
    expect(await screen.findByText(/No sufficiently similar/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Journal' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Journal offline')
    vi.mocked(api.listSessions).mockResolvedValue([])
    vi.mocked(api.fetchSessionMatches).mockResolvedValue({ hour: forecast.hourly[0].timestamp, status: 'insufficient_conditions', matches: [] })
    await userEvent.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText(/Not enough forecast data/)).toBeInTheDocument()
  })
})
