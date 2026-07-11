// Google Search Trends interest-over-time chart, drawn as inline SVG so we
// don't need a chart dependency. Data shape: TrendsResponse in schemas.py.

const W = 560
const H = 200
const PAD = { top: 16, right: 12, bottom: 28, left: 34 }

export default function TrendsChart({ data }) {
  if (!data) return <div className="panel-empty">Loading trends…</div>

  const pts = data.points
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (i) => PAD.left + (i / (pts.length - 1)) * innerW
  const y = (v) => PAD.top + (1 - v / 100) * innerH

  const line = pts.map((p, i) => `${x(i)},${y(p.interest)}`).join(' ')
  const area = `${PAD.left},${y(0)} ${line} ${x(pts.length - 1)},${y(0)}`
  const spikeIdx = data.spike_date
    ? pts.findIndex((p) => p.date === data.spike_date)
    : -1

  return (
    <div className="trends-chart">
      <div className="trends-meta">
        <code>"{data.query}"</code>
        <span className="trends-region">{data.region}</span>
        {data.spike_detected && (
          <span className="spike-chip">▲ spike {data.spike_date}</span>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Search interest over time">
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line
              x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)}
              className="chart-grid"
            />
            <text x={PAD.left - 6} y={y(v) + 3} className="chart-tick" textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        <polygon points={area} className="chart-area" />
        <polyline points={line} className="chart-line" fill="none" />
        {spikeIdx >= 0 && (
          <circle
            cx={x(spikeIdx)} cy={y(pts[spikeIdx].interest)} r="4.5"
            className="chart-spike"
          />
        )}
        {pts.map((p, i) =>
          i % 2 === 0 ? (
            <text key={p.date} x={x(i)} y={H - 8} className="chart-tick" textAnchor="middle">
              {p.date.slice(5)}
            </text>
          ) : null
        )}
      </svg>
    </div>
  )
}
