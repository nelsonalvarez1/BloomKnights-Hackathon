// Fleet intelligence — ~10 monitored locations per corporation, each with a
// satellite-derived occupancy read. Renders a heatmap of the fleet plus the
// aggregated company-wide numbers the revenue model actually consumes.

function occColor(o) {
  // orange heat ramp keyed to occupancy
  const a = 0.12 + o * 0.78
  return `rgba(245, 136, 0, ${a.toFixed(3)})`
}

const statusLabel = {
  surging: 'Surging', rising: 'Rising', stable: 'Stable', cooling: 'Cooling',
}

export default function StoreFleet({ fusion }) {
  if (!fusion) return <div className="panel-empty">Locating fleet…</div>
  const { fleet, agg } = fusion

  return (
    <div className="fleet">
      <div className="fleet-summary">
        <Stat k="Avg Occupancy" v={`${Math.round(agg.avgOccupancy * 100)}%`} />
        <Stat k="Peak Occupancy" v={`${Math.round(agg.peakOccupancy * 100)}%`} />
        <Stat
          k="Fleet Growth"
          v={`${agg.avgGrowth >= 0 ? '+' : ''}${Math.round(agg.avgGrowth * 100)}%`}
          tone={agg.avgGrowth >= 0 ? 'pos' : 'neg'}
        />
        <Stat k="Sites Rising" v={`${agg.surging}/${agg.total}`} />
      </div>

      <div className="fleet-grid">
        {fleet.map((f) => (
          <div className="fleet-cell" key={f.id} title={`${f.region} · ${f.vehicles}/${f.capacity} vehicles`}>
            <div className="fleet-heat" style={{ background: occColor(f.occupancy) }}>
              <span className="fleet-occ">{Math.round(f.occupancy * 100)}</span>
            </div>
            <span className="fleet-store">{f.label}</span>
            <span className="fleet-region">{f.region}</span>
            <span className={`fleet-status st-${f.status}`}>{statusLabel[f.status]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Stat({ k, v, tone = 'neutral' }) {
  return (
    <div className="fleet-stat">
      <span className="fleet-stat-k">{k}</span>
      <span className={`fleet-stat-v tone-${tone}`}>{v}</span>
    </div>
  )
}
