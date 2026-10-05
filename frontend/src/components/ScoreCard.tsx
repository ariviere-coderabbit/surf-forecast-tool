import type { BestWindow, HourlyConditions, SpotProfile } from '../api/types'
import { formatLocal } from '../utils/time'

interface Props {
  current: HourlyConditions
  profile: SpotProfile
  bestWindow?: BestWindow | null
  timezone: string
}

function scoreColor(score: number): string {
  if (score >= 8) return '#2ecc71'
  if (score >= 6) return '#f39c12'
  if (score >= 4) return '#e67e22'
  return '#e74c3c'
}

function bar(value: number | undefined | null, label: string) {
  if (value == null) return null
  const pct = Math.round(value * 100)
  return (
    <div style={{ marginBottom: '0.4rem' }}>
      <span style={{ display: 'inline-block', width: 110, fontSize: '0.85rem', color: '#555' }}>{label}</span>
      <span style={{ display: 'inline-block', width: `${pct}%`, maxWidth: 160, height: 10, background: '#0077cc', borderRadius: 3, verticalAlign: 'middle' }} />
      <span style={{ marginLeft: '0.4rem', fontSize: '0.8rem', color: '#333' }}>{pct}%</span>
    </div>
  )
}

export default function ScoreCard({ current, profile, bestWindow, timezone }: Props) {
  const score = current.score
  const conf = current.confidence

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: '1rem', marginBottom: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginBottom: '0.75rem' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', fontWeight: 700, color: score != null ? scoreColor(score) : '#aaa', lineHeight: 1 }}>
            {score != null ? score.toFixed(1) : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#666' }}>/ 10</div>
          <div style={{ fontSize: '0.8rem', color: '#888', marginTop: 2 }}>
            {conf != null ? `${Math.round(conf * 100)}% confidence` : '—'}
          </div>
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: '1.1rem', marginBottom: '0.2rem' }}>{profile.name}</div>
          <div style={{ fontSize: '0.85rem', color: '#555' }}>
            {formatLocal(current.timestamp, timezone)}
          </div>
          {!profile.calibrated && (
            <div style={{ fontSize: '0.75rem', color: '#c0392b', marginTop: 4 }}>
              ⚠ Score is approximate — profile not field-calibrated
            </div>
          )}
        </div>
      </div>

      <div style={{ borderTop: '1px solid #eee', paddingTop: '0.6rem' }}>
        <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.3rem', color: '#333' }}>Component breakdown</div>
        {bar(current.score_wave_height, 'Wave height')}
        {bar(current.score_wave_period, 'Wave period')}
        {bar(current.score_wind, 'Wind')}
        {bar(current.score_direction, 'Direction')}
      </div>

      {bestWindow && (
        <div style={{ marginTop: '0.75rem', borderTop: '1px solid #eee', paddingTop: '0.6rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Best window: </span>
          <span style={{ fontSize: '0.85rem' }}>
            {formatLocal(bestWindow.start, timezone)} – {formatLocal(bestWindow.end, timezone)}
            {' '}(avg {bestWindow.mean_score.toFixed(1)}, peak {bestWindow.peak_score.toFixed(1)})
          </span>
        </div>
      )}
    </div>
  )
}
