import type { GeoCandidate } from '../api/types'

interface Props {
  candidates: GeoCandidate[]
  onSelect: (c: GeoCandidate) => void
}

export default function CandidateList({ candidates, onSelect }: Props) {
  if (candidates.length === 0) return null

  return (
    <div style={{ marginBottom: '1rem' }}>
      <p style={{ margin: '0 0 0.5rem', fontWeight: 600 }}>
        Multiple locations found — please select one:
      </p>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {candidates.map(c => (
          <li key={c.id} style={{ marginBottom: '0.25rem' }}>
            <button
              onClick={() => onSelect(c)}
              style={{
                background: 'none',
                border: '1px solid #0077cc',
                borderRadius: 4,
                padding: '0.35rem 0.75rem',
                cursor: 'pointer',
                color: '#0077cc',
                fontSize: '0.95rem',
              }}
            >
              {c.name}
              {c.admin1 ? `, ${c.admin1}` : ''}
              {c.country ? ` — ${c.country}` : ''}
              <span style={{ color: '#666', fontSize: '0.8rem', marginLeft: '0.5rem' }}>
                ({c.latitude.toFixed(2)}, {c.longitude.toFixed(2)})
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
