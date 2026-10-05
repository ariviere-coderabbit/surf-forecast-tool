import { useState } from 'react'
import { geocode, fetchForecast } from './api/client'
import type { ForecastResponse, GeoCandidate, GeocodeResponse } from './api/types'
import CandidateList from './components/CandidateList'
import Disclaimers from './components/Disclaimers'
import HourlyTable from './components/HourlyTable'
import ProviderComparison from './components/ProviderComparison'
import ScoreCard from './components/ScoreCard'
import SearchBar from './components/SearchBar'
import Journal from './components/Journal'

type Phase = 'idle' | 'geocoding' | 'candidates' | 'forecasting' | 'done' | 'error'

export default function App() {
  const [location, setLocation] = useState<GeoCandidate>()
  const [phase, setPhase] = useState<Phase>('idle')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [geocodeResult, setGeocodeResult] = useState<GeocodeResponse | null>(null)
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)

  async function handleSearch(query: string) {
    setPhase('geocoding')
    setErrorMsg(null)
    setGeocodeResult(null)
    setForecast(null)
    setLocation(undefined)
    try {
      const result = await geocode(query)
      if (result.candidates.length === 0) {
        setErrorMsg('No locations found. Try a more specific search.')
        setPhase('error')
        return
      }
      if (result.selected) {
        await loadForecast(result.selected)
      } else {
        setGeocodeResult(result)
        setPhase('candidates')
      }
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e))
      setPhase('error')
    }
  }

  async function loadForecast(candidate: GeoCandidate) {
    setLocation(candidate)
    setPhase('forecasting')
    setGeocodeResult(null)
    try {
      const f = await fetchForecast(candidate)
      setForecast(f)
      setPhase('done')
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e))
      setPhase('error')
    }
  }

  const loading = phase === 'geocoding' || phase === 'forecasting'
  const currentHour = forecast?.hourly.find(h => new Date(h.timestamp).getTime() >= Math.floor(Date.now() / 3600000) * 3600000) ?? forecast?.hourly[0]
  const timezone = forecast?.location.timezone ?? 'UTC'

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 920, margin: '0 auto', padding: '1rem' }}>
      <h1 style={{ marginBottom: '0.25rem' }}>🏄 Surf Forecast</h1>
      <p style={{ margin: '0 0 1rem', color: '#555', fontSize: '0.9rem' }}>
        Wave, wind, and surfability forecast powered by Open-Meteo &amp; NOAA GFS-Wave.
      </p>

      <SearchBar onSearch={handleSearch} loading={loading} />

      {phase === 'geocoding' && <p>Searching for location…</p>}
      {phase === 'forecasting' && <p>Fetching forecast…</p>}

      {phase === 'candidates' && geocodeResult && (
        <CandidateList candidates={geocodeResult.candidates} onSelect={loadForecast} />
      )}

      {phase === 'error' && errorMsg && (
        <div style={{ background: '#f8d7da', border: '1px solid #f5c6cb', borderRadius: 6, padding: '0.75rem', marginBottom: '1rem' }}>
          {errorMsg}
        </div>
      )}

      {phase === 'done' && forecast && currentHour && (
          <ScoreCard
            current={currentHour}
            profile={forecast.spot_profile}
            bestWindow={forecast.best_window}
            timezone={timezone}
          />
      )}
      <Journal location={location} forecast={forecast ?? undefined} />
      {phase === 'done' && forecast && (
        <>
          <HourlyTable hourly={forecast.hourly} timezone={timezone} />
          <ProviderComparison providers={forecast.providers} timezone={timezone} />
          <Disclaimers
            notices={forecast.notices}
            warnings={forecast.warnings}
            errors={forecast.errors}
          />
        </>
      )}
    </main>
  )
}
