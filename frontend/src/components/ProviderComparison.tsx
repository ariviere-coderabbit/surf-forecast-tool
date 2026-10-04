import type { ProviderSeries } from '../api/types'
import { formatTime } from '../utils/time'

interface Props {
  providers: ProviderSeries[]
  timezone: string
}

const TH: React.CSSProperties = {
  padding: '0.3rem 0.5rem',
  background: '#f5f5f5',
  borderBottom: '2px solid #ddd',
  fontSize: '0.78rem',
  whiteSpace: 'nowrap',
  textAlign: 'left',
}

const TD: React.CSSProperties = {
  padding: '0.25rem 0.5rem',
  borderBottom: '1px solid #eee',
  fontSize: '0.8rem',
  whiteSpace: 'nowrap',
}

function statusBadge(status: string) {
  const color = status === 'ok' ? '#27ae60' : status === 'partial' ? '#f39c12' : '#e74c3c'
  return (
    <span style={{ background: color, color: '#fff', borderRadius: 3, padding: '1px 5px', fontSize: '0.7rem', marginLeft: 6 }}>
      {status}
    </span>
  )
}

function v(n: number | undefined | null, d = 1): string {
  if (n === undefined || n === null) return '—'
  return n.toFixed(d)
}

export default function ProviderComparison({ providers, timezone }: Props) {
  if (providers.length === 0) return null

  return (
    <section style={{ marginBottom: '1rem' }}>
      <h3 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>Provider data</h3>
      {providers.map(p => (
        <details key={`${p.provider}-${p.model}`} style={{ marginBottom: '0.75rem' }}>
          <summary style={{ cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600 }}>
            {p.provider} / {p.model}
            {statusBadge(p.status)}
            {p.error && <span style={{ color: '#e74c3c', fontWeight: 400, marginLeft: 8, fontSize: '0.8rem' }}>{p.error}</span>}
          </summary>

          {p.hourly.length > 0 && (
            <div style={{ overflowX: 'auto', marginTop: '0.5rem' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 600 }}>
                <thead>
                  <tr>
                    <th style={TH}>Time</th>
                    <th style={TH}>Hs (m)</th>
                    <th style={TH}>Period (s)</th>
                    <th style={TH}>Dir (°)</th>
                    <th style={TH}>Swell (m)</th>
                    <th style={TH}>Wind (m/s)</th>
                    <th style={TH}>W. dir</th>
                    <th style={TH}>Grid pt.</th>
                    <th style={TH}>Dist. (km)</th>
                  </tr>
                </thead>
                <tbody>
                  {p.hourly.slice(0, 48).map(h => (
                    <tr key={h.timestamp}>
                      <td style={TD}>{formatTime(h.timestamp, timezone)}</td>
                      <td style={TD}>{v(h.wave_height_m, 2)}</td>
                      <td style={TD}>{v(h.wave_period_s)}</td>
                      <td style={TD}>{v(h.wave_direction_deg, 0)}</td>
                      <td style={TD}>{v(h.swell_height_m, 2)}</td>
                      <td style={TD}>{v(h.wind_speed_mps)}</td>
                      <td style={TD}>{v(h.wind_direction_deg, 0)}</td>
                      <td style={TD}>
                        {h.grid_lat !== undefined && h.grid_lon !== undefined
                          ? `${h.grid_lat.toFixed(2)}, ${h.grid_lon.toFixed(2)}`
                          : '—'}
                      </td>
                      <td style={TD}>{v(h.sampling_distance_km, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {p.hourly.length > 48 && (
                <p style={{ fontSize: '0.75rem', color: '#888', margin: '0.25rem 0 0' }}>
                  Showing first 48 of {p.hourly.length} hours.
                </p>
              )}
            </div>
          )}
        </details>
      ))}
      <p style={{ fontSize: '0.75rem', color: '#888' }}>
        Grid pt. and Dist. show which model grid point was used and how far it is from your location.
        Larger distances mean lower confidence in local accuracy.
      </p>
    </section>
  )
}
