// Schematic proximity map: the store at center, range rings, jet events
// plotted by real bearing/distance from the store. Not a tile map on
// purpose — no external tiles, nothing to break on stage.

const SIZE = 300
const C = SIZE / 2
const MAX_MILES = 20
const RINGS = [5, 10, 15, 20]

function project(store, e) {
  // Equirectangular offset from store, scaled so MAX_MILES hits the edge.
  const milesPerDegLat = 69
  const milesPerDegLon = 69 * Math.cos((store.lat * Math.PI) / 180)
  const dx = (e.lon - store.lon) * milesPerDegLon
  const dy = (e.lat - store.lat) * milesPerDegLat
  const scale = (C - 18) / MAX_MILES
  return { x: C + dx * scale, y: C - dy * scale }
}

export default function JetMap({ data, store }) {
  if (!data || !store) return <div className="panel-empty">Loading jets…</div>

  return (
    <div className="jet-map">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label="Jet activity near store">
        {RINGS.map((r) => (
          <g key={r}>
            <circle
              cx={C} cy={C} r={(r / MAX_MILES) * (C - 18)}
              className="map-ring"
            />
            <text x={C + 3} y={C - (r / MAX_MILES) * (C - 18) - 3} className="map-ring-label">
              {r}mi
            </text>
          </g>
        ))}
        <rect x={C - 5} y={C - 5} width="10" height="10" className="map-store" />
        {data.events.map((e, i) => {
          const p = project(store, e)
          return (
            <g key={i} className={e.event_type === 'landing' ? 'jet-landing' : 'jet-prox'}>
              <text x={p.x} y={p.y + 5} textAnchor="middle" className="jet-marker">✈</text>
            </g>
          )
        })}
      </svg>
      <ul className="jet-events">
        {data.events.length === 0 && (
          <li className="jet-none">No corporate jet activity in window</li>
        )}
        {data.events.map((e, i) => (
          <li key={i}>
            <code>{e.tail_number}</code> {e.event_type} · {e.airport} ·{' '}
            {e.distance_miles} mi · {e.timestamp.slice(0, 16).replace('T', ' ')}
          </li>
        ))}
      </ul>
      {data.proximity_flag && <div className="prox-flag">PROXIMITY FLAG SET</div>}
    </div>
  )
}
