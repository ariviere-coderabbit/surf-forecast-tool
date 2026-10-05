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

export async function listSessions(): Promise<import('./types').SurfSession[]> {
  return request('/sessions')
}

async function mutateSession<T>(path: string, method: string, data?: import('./types').SessionInput): Promise<T> {
  const response = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: data ? JSON.stringify(data) : undefined,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const message = Array.isArray(body.detail)
      ? body.detail.map((item: { msg: string }) => item.msg).join('; ')
      : body.detail
    throw new Error(message || `Could not save journal changes (HTTP ${response.status})`)
  }
  return response.status === 204 ? undefined as T : response.json()
}

export function saveSession(data: import('./types').SessionInput, id?: string): Promise<import('./types').SurfSession> {
  return mutateSession(id ? `/sessions/${encodeURIComponent(id)}` : '/sessions', id ? 'PUT' : 'POST', data)
}

export function deleteSession(id: string): Promise<void> {
  return mutateSession(`/sessions/${encodeURIComponent(id)}`, 'DELETE')
}

export function fetchSessionMatches(location: GeoCandidate, hour: string): Promise<import('./types').MatchesResponse> {
  return request('/session-matches', { lat: String(location.latitude), lon: String(location.longitude), hour })
}
