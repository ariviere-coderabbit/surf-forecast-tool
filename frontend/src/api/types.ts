/** TypeScript types mirroring the FastAPI backend Pydantic models. */

export interface GeoCandidate {
  id: number
  name: string
  country: string
  country_code: string
  admin1?: string | null
  latitude: number
  longitude: number
  timezone: string
  population?: number | null
}

export interface GeocodeResponse {
  query: string
  candidates: GeoCandidate[]
  selected?: GeoCandidate | null
}

export interface HourlyConditions {
  timestamp: string           // ISO-8601 UTC
  wave_height_m?: number | null
  wave_period_s?: number | null
  wave_direction_deg?: number | null
  wind_wave_height_m?: number | null
  wind_wave_period_s?: number | null
  wind_wave_direction_deg?: number | null
  swell_height_m?: number | null
  swell_period_s?: number | null
  swell_direction_deg?: number | null
  wind_speed_mps?: number | null
  wind_direction_deg?: number | null
  wind_gust_mps?: number | null
  sea_level_m?: number | null
  score?: number | null              // 0–10
  confidence?: number | null         // 0–1
  score_wave_height?: number | null
  score_wave_period?: number | null
  score_wind?: number | null
  score_direction?: number | null
}

export interface ProviderHourly {
  timestamp: string
  wave_height_m?: number | null
  wave_period_s?: number | null
  wave_direction_deg?: number | null
  swell_height_m?: number | null
  swell_period_s?: number | null
  wind_speed_mps?: number | null
  wind_direction_deg?: number | null
  grid_lat?: number | null
  grid_lon?: number | null
  sampling_distance_km?: number | null
}

export interface ProviderSeries {
  provider: string
  model: string
  status: 'ok' | 'error' | 'partial'
  error?: string | null
  hourly: ProviderHourly[]
}

export interface BestWindow {
  start: string
  end: string
  mean_score: number
  peak_score: number
}

export interface SpotProfile {
  name: string
  latitude: number
  longitude: number
  ideal_swell_direction_deg?: number | null
  ideal_swell_direction_tolerance_deg: number
  ideal_wave_height_min_m: number
  ideal_wave_height_max_m: number
  ideal_period_min_s: number
  ideal_wind_direction_deg?: number | null
  ideal_wind_direction_tolerance_deg: number
  max_wind_speed_mps: number
  calibrated: boolean
}

export interface ForecastResponse {
  location: GeoCandidate
  spot_profile: SpotProfile
  generated_at: string
  hourly: HourlyConditions[]
  providers: ProviderSeries[]
  best_window?: BestWindow | null
  errors: string[]
  warnings: string[]
  notices: string[]
}

export type SessionRating = 'poor' | 'okay' | 'good' | 'great'
export interface Observations {
  wave_height_m?: number | null
  wave_period_s?: number | null
  wave_direction_deg?: number | null
  wind_speed_mps?: number | null
  wind_direction_deg?: number | null
  tide_stage: 'low' | 'mid' | 'high' | 'unknown'
  tide_movement: 'rising' | 'falling' | 'unknown'
}
export interface SessionInput {
  location: GeoCandidate
  session_at: string
  note: string
  rating: SessionRating
  observations: Observations
}
export interface SurfSession extends SessionInput {
  id: string
  created_at: string
  updated_at: string
  conditions_status: 'available' | 'hour_unavailable' | 'provider_unavailable'
  snapshot: {
    captured_at: string
    generated_at: string
    conditions: HourlyConditions
    providers: ProviderSeries[]
    notices: string[]
  } | null
}
export interface ConditionComparison {
  field: string
  session_value: number
  forecast_value: number
  difference: number
  tolerance: number
  source: 'observed' | 'modeled'
}
export interface MatchesResponse {
  hour: string
  status: 'available' | 'hour_unavailable' | 'provider_unavailable' | 'insufficient_conditions'
  matches: { session: SurfSession; distance: number; comparisons: ConditionComparison[] }[]
}
