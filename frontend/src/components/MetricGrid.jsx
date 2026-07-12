// The institutional metric wall — ~28 derived quant metrics grouped by the
// funnel stage they belong to. Each tile animates in; the number itself
// carries the tone (green up / red down / orange edge).

const GROUPS = ['Supply', 'Activity', 'Demand', 'Forecast', 'Edge']

export default function MetricGrid({ fusion }) {
  if (!fusion) return <div className="panel-empty">Computing metrics…</div>
  return (
    <div className="metric-wall">
      {GROUPS.map((g) => {
        const items = fusion.metrics.filter((m) => m.group === g)
        if (!items.length) return null
        return (
          <div className="metric-group" key={g}>
            <h3 className="metric-group-title">{g}</h3>
            <div className="metric-tiles">
              {items.map((m, i) => (
                <div
                  className="metric-tile"
                  key={m.name}
                  style={{ animationDelay: `${0.03 * i}s` }}
                >
                  <span className="metric-name">{m.name}</span>
                  <span className={`metric-value tone-${m.tone}`}>{m.value}</span>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
