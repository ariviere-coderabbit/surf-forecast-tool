/** TypeScript types mirroring the FastAPI backend Pydantic models. */

export interface GeoCandidate {
  id: number
  name: string
  country: string
  country_code: string
  admin1?: string
  latitude: number
  longitude: number
  timezone: string
  population?: number
}

export interface GeocodeResponse {
  query: string
  candidates: GeoCandidate[]
  selected?: GeoCandidate
}

export interface HourlyConditions {
  timestamp: string           // ISO-8601 UTC
  wave_height_m?: number
  wave_period_s?: number
  wave_direction_deg?: number
  wind_wave_height_m?: number
  wind_wave_period_s?: number
  wind_wave_direction_deg?: number
  swell_height_m?: number
  swell_period_s?: number
  swell_direction_deg?: number
  wind_speed_mps?: number
  wind_direction_deg?: number
  wind_gust_mps?: number
  sea_level_m?: number
  score?: number              // 0–10
  confidence?: number         // 0–1
  score_wave_height?: number
  score_wave_period?: number
  score_wind?: number
  score_direction?: number
}

export interface ProviderHourly {
  timestamp: string
  wave_height_m?: number
  wave_period_s?: number
  wave_direction_deg?: number
  swell_height_m?: number
  swell_period_s?: number
  wind_speed_mps?: number
  wind_direction_deg?: number
  grid_lat?: number
  grid_lon?: number
  sampling_distance_km?: number
}

export interface ProviderSeries {
  provider: string
  model: string
  status: 'ok' | 'error' | 'partial'
  error?: string
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
  ideal_swell_direction_deg?: number
  ideal_swell_direction_tolerance_deg: number
  ideal_wave_height_min_m: number
  ideal_wave_height_max_m: number
  ideal_period_min_s: number
  ideal_wind_direction_deg?: number
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
  best_window?: BestWindow
  errors: string[]
  warnings: string[]
  notices: string[]
}
