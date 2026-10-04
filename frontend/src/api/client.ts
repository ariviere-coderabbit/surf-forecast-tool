import type { ForecastResponse, GeoCandidate, GeocodeResponse } from './types'

const BASE = '/api'

async function request<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function geocode(query: string, country?: string): Promise<GeocodeResponse> {
  const params: Record<string, string> = { q: query }
  if (country) params.country = country
  return request<GeocodeResponse>('/geocode', params)
}

export async function fetchForecast(candidate: GeoCandidate): Promise<ForecastResponse> {
  return request<ForecastResponse>('/forecast', {
    lat: String(candidate.latitude),
    lon: String(candidate.longitude),
    timezone: candidate.timezone,
    name: candidate.name,
    country: candidate.country,
    country_code: candidate.country_code,
  })
}
