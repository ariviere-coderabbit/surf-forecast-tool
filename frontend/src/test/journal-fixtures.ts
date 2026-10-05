import type { ForecastResponse, SurfSession } from '../api/types'
export const location = { id: 1, name: 'Jacó', country: 'Costa Rica', country_code: 'CR', latitude: 9.613, longitude: -84.628, timezone: 'America/Costa_Rica' }
export const session: SurfSession = {
  id: 'session-one', location, session_at: '2024-01-15T12:30:15Z', note: 'Clean waves, great day.', rating: 'great',
  observations: { tide_stage: 'high', tide_movement: 'falling' },
  created_at: '2024-01-15T14:00:00Z', updated_at: '2024-01-15T14:00:00Z',
  conditions_status: 'hour_unavailable', snapshot: null,
}
export const forecast: ForecastResponse = {
  location, generated_at: '2024-01-15T12:00:00Z',
  spot_profile: { name: 'Jacó', latitude: 9.613, longitude: -84.628,
    ideal_swell_direction_tolerance_deg: 45, ideal_wave_height_min_m: 0.5, ideal_wave_height_max_m: 2.5,
    ideal_period_min_s: 8, ideal_wind_direction_tolerance_deg: 45, max_wind_speed_mps: 10, calibrated: false },
  hourly: [{ timestamp: '2024-01-15T12:00:00Z', wave_height_m: 1.2, wave_period_s: 10, wind_speed_mps: 3 },
    { timestamp: '2024-01-15T13:00:00Z', wave_height_m: 1.3, wave_period_s: 10, wind_speed_mps: 3 }],
  providers: [], errors: [], warnings: [], notices: [],
}
