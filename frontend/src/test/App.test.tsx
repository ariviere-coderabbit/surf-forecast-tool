import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as client from '../api/client'
import type { ForecastResponse, GeocodeResponse } from '../api/types'

vi.mock('../api/client')

const mockClient = vi.mocked(client)

function makeCandidate(name = 'Jacó', country = 'Costa Rica') {
  return {
    id: country === 'Costa Rica' ? 1 : 2, name, country, country_code: 'CR',
    latitude: 9.613, longitude: -84.628,
    timezone: 'America/Costa_Rica',
  }
}

function makeForecast(overrides: Partial<ForecastResponse> = {}): ForecastResponse {
  return {
    location: makeCandidate(),
    spot_profile: {
      name: 'Jacó', latitude: 9.613, longitude: -84.628,
      ideal_swell_direction_tolerance_deg: 50,
      ideal_wave_height_min_m: 0.5, ideal_wave_height_max_m: 2.0,
      ideal_period_min_s: 8,
      ideal_wind_direction_tolerance_deg: 45,
      max_wind_speed_mps: 8, calibrated: false,
    },
    generated_at: '2024-01-15T12:00:00Z',
    hourly: [{
      timestamp: '2024-01-15T12:00:00Z',
      wave_height_m: 1.2, wave_period_s: 12, wave_direction_deg: 200,
      swell_height_m: 1.0, swell_direction_deg: 210,
      wind_speed_mps: 3, wind_direction_deg: 70,
      score: 7.5, confidence: 0.9,
      score_wave_height: 0.9, score_wave_period: 0.8, score_wind: 0.7, score_direction: 0.85,
    }],
    providers: [],
    notices: ['Scores are heuristic.'],
    warnings: [],
    errors: [],
    ...overrides,
  }
}

describe('App', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(client.fetchSessionMatches).mockResolvedValue({ hour: '2024-01-15T12:00:00Z', status: 'available', matches: [] })
  })

  it('shows loading state while geocoding', async () => {
    let resolve: (v: GeocodeResponse) => void
    mockClient.geocode.mockReturnValue(new Promise(r => { resolve = r }))
    render(<App />)
    await userEvent.type(screen.getByRole('textbox'), 'Jaco')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))
    expect(screen.getByText(/searching for location/i)).toBeInTheDocument()
    resolve!({ query: 'Jaco', candidates: [], selected: undefined })
  })

  it('shows forecast on successful single-result geocode', async () => {
    const candidate = makeCandidate()
    mockClient.geocode.mockResolvedValue({ query: 'Jaco', candidates: [candidate], selected: candidate })
    mockClient.fetchForecast.mockResolvedValue(makeForecast())

    render(<App />)
    await userEvent.type(screen.getByRole('textbox'), 'Jaco')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => expect(screen.getAllByText('7.5')[0]).toBeInTheDocument())
    expect(screen.getByText(/jacó/i)).toBeInTheDocument()
  })

  it('shows candidate picker for ambiguous geocode', async () => {
    const candidates = [makeCandidate('Jacó', 'Costa Rica'), makeCandidate('Jacó', 'Mexico')]
    mockClient.geocode.mockResolvedValue({ query: 'Jaco', candidates, selected: undefined })

    render(<App />)
    await userEvent.type(screen.getByRole('textbox'), 'Jaco')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => expect(screen.getByText(/multiple locations/i)).toBeInTheDocument())
    expect(screen.getAllByRole('button').length).toBeGreaterThan(1)
  })

  it('shows forecast after selecting a candidate', async () => {
    const candidate = makeCandidate()
    const candidates = [candidate, makeCandidate('Jacó', 'Mexico')]
    mockClient.geocode.mockResolvedValue({ query: 'Jaco', candidates, selected: undefined })
    mockClient.fetchForecast.mockResolvedValue(makeForecast())

    render(<App />)
    await userEvent.type(screen.getByRole('textbox'), 'Jaco')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => screen.getByText(/multiple locations/i))
    await userEvent.click(screen.getByRole('button', { name: /Jacó — Costa Rica/ }))
    await waitFor(() => expect(screen.getAllByText('7.5')[0]).toBeInTheDocument())
  })

  it('shows error message when geocode fails', async () => {
    mockClient.geocode.mockRejectedValue(new Error('No locations found'))
    render(<App />)
    await userEvent.type(screen.getByRole('textbox'), 'xyznotaplace')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))
    await waitFor(() => expect(screen.getByText(/no locations found/i)).toBeInTheDocument())
  })

  it('shows partial forecast with warnings when NOAA missing', async () => {
    const candidate = makeCandidate()
    mockClient.geocode.mockResolvedValue({ query: 'Jaco', candidates: [candidate], selected: candidate })
    mockClient.fetchForecast.mockResolvedValue(
      makeForecast({ warnings: ['NOAA GFS-Wave data not yet cached'] })
    )

    render(<App />)
    await userEvent.type(screen.getByRole('textbox'), 'Jaco')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => screen.getAllByText('7.5')[0])
    expect(screen.getByText(/NOAA GFS-Wave data not yet cached/)).toBeInTheDocument()
  })
  it('renders provider nulls returned by the live API without losing the journal', async () => {
    const candidate = makeCandidate()
    mockClient.geocode.mockResolvedValue({ query: 'Jaco', candidates: [candidate], selected: candidate })
    mockClient.fetchForecast.mockResolvedValue(makeForecast({
      hourly: [{ timestamp: '2024-01-15T12:00:00Z', score: null, confidence: null, score_wind: null }],
      providers: [{ provider: 'open-meteo', model: 'best_match', status: 'ok', hourly: [{
        timestamp: '2024-01-15T12:00:00Z', grid_lat: null, grid_lon: null, wave_height_m: null,
        sampling_distance_km: null, wind_speed_mps: 3,
      }] }],
    }))
    render(<App />)
    await userEvent.type(screen.getByRole('textbox'), 'Jaco')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('Provider data')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log a session' })).toBeInTheDocument()
    expect(await screen.findByText(/No sufficiently similar sessions/)).toBeInTheDocument()
  })

})
