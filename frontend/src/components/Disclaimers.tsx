interface Props {
  notices: string[]
  warnings: string[]
  errors: string[]
}

const boxStyle = (color: string): React.CSSProperties => ({
  background: color,
  border: `1px solid ${color === '#fff3cd' ? '#ffc107' : color === '#f8d7da' ? '#f5c6cb' : '#bee5eb'}`,
  borderRadius: 6,
  padding: '0.6rem 0.85rem',
  marginBottom: '0.5rem',
  fontSize: '0.85rem',
})

export default function Disclaimers({ notices, warnings, errors }: Props) {
  return (
    <section style={{ marginTop: '1.5rem' }}>
      <h3 style={{ fontSize: '0.95rem', marginBottom: '0.4rem', color: '#555' }}>
        Source details &amp; limitations
      </h3>

      {errors.map((e, i) => (
        <div key={i} style={boxStyle('#f8d7da')}>
          <strong>Provider error:</strong> {e}
        </div>
      ))}

      {warnings.map((w, i) => (
        <div key={i} style={boxStyle('#fff3cd')}>
          ⚠ {w}
        </div>
      ))}

      {notices.map((n, i) => (
        <div key={i} style={boxStyle('#d1ecf1')}>
          ℹ {n}
        </div>
      ))}

      <div style={{ fontSize: '0.78rem', color: '#888', marginTop: '0.5rem', lineHeight: 1.5 }}>
        <strong>Attribution:</strong> Wave data: Open-Meteo Marine API (ICON-Wave, DWD) &amp; NOAA/NCEP GFS-Wave 0.16°.
        Wind: Open-Meteo Forecast API. Geocoding: Open-Meteo Geocoding API. All free, non-commercial use.
        <br />
        Merged values use circular-mean directions and provider-preferred period statistics.
        NOAA data is cached and refreshed every 6 hours in the background.
      </div>
    </section>
  )
}
