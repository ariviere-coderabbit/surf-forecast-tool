import type { CSSProperties } from 'react'
import type { HourlyConditions } from '../api/types'
import { formatTime } from '../utils/time'

interface Props {
  hourly: HourlyConditions[]
  timezone: string
}

/** Display a value or an em-dash when missing, distinguishing zero from absent. */
function val(v: number | undefined | null, decimals = 1, unit = ''): string {
  if (v === undefined || v === null) return '—'
  return `${v.toFixed(decimals)}${unit}`
}

function scoreCell(score: number | undefined | null) {
  if (score == null) return <td>—</td>
  const color = score >= 8 ? '#27ae60' : score >= 6 ? '#f39c12' : score >= 4 ? '#e67e22' : '#e74c3c'
  return <td style={{ fontWeight: 600, color }}>{score.toFixed(1)}</td>
}

const TH: CSSProperties = {
  padding: '0.35rem 0.5rem',
  background: '#f5f5f5',
  borderBottom: '2px solid #ddd',
  whiteSpace: 'nowrap',
  fontSize: '0.8rem',
  textAlign: 'left',
}

const TD: CSSProperties = {
  padding: '0.3rem 0.5rem',
  borderBottom: '1px solid #eee',
  fontSize: '0.85rem',
  whiteSpace: 'nowrap',
}

export default function HourlyTable({ hourly, timezone }: Props) {
  return (
    <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 700 }}>
        <thead>
          <tr>
            <th style={TH}>Time ({timezone})</th>
            <th style={TH}>Score</th>
            <th style={TH}>Conf.</th>
            <th style={TH}>Hs (m)</th>
            <th style={TH}>Period (s)</th>
            <th style={TH}>Dir (°)</th>
            <th style={TH}>Swell (m)</th>
            <th style={TH}>Sw. per.</th>
            <th style={TH}>Wind (m/s)</th>
            <th style={TH}>W. dir</th>
            <th style={TH}>Sea lvl (m)</th>
          </tr>
        </thead>
        <tbody>
          {hourly.map(h => (
            <tr key={h.timestamp}>
              <td style={TD}>{formatTime(h.timestamp, timezone)}</td>
              {scoreCell(h.score)}
              <td style={TD}>{h.confidence != null ? `${Math.round(h.confidence * 100)}%` : '—'}</td>
              <td style={TD}>{val(h.wave_height_m, 2, ' m')}</td>
              <td style={TD}>{val(h.wave_period_s, 1, ' s')}</td>
              <td style={TD}>{val(h.wave_direction_deg, 0, '°')}</td>
              <td style={TD}>{val(h.swell_height_m, 2, ' m')}</td>
              <td style={TD}>{val(h.swell_period_s, 1, ' s')}</td>
              <td style={TD}>{val(h.wind_speed_mps, 1, ' m/s')}</td>
              <td style={TD}>{val(h.wind_direction_deg, 0, '°')}</td>
              <td style={TD}>{h.sea_level_m !== undefined && h.sea_level_m !== null ? `${h.sea_level_m.toFixed(2)} m ⚠` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: '0.75rem', color: '#888', margin: '0.3rem 0 0' }}>
        ⚠ Sea level is modeled output, not a tide table. — = missing measurement (not zero).
      </p>
    </div>
  )
}
