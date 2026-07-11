// The money-shot panel: our signal fired day 0, the market found out N days
// later via EDGAR. Every filing links to the real document.

export default function EdgarTimeline({ data }) {
  if (!data) return <div className="panel-empty">Loading EDGAR…</div>

  const day0 = new Date(data.signal_date)
  const dayOf = (iso) =>
    Math.round((new Date(iso) - day0) / (1000 * 60 * 60 * 24))
  const maxDay = Math.max(1, ...data.filings.map((f) => dayOf(f.filed_at)))
  const pos = (day) => 6 + (day / maxDay) * 88 // % along the track

  return (
    <div className="edgar-timeline">
      <div className="edgar-headline">
        <span className="lead-days">{data.lead_days}</span>
        <span className="lead-label">
          days ahead of the first filing
          <small>
            {data.company} · CIK {data.cik}
          </small>
        </span>
      </div>

      <div className="timeline-track">
        <div className="timeline-bar" />
        <div className="timeline-node signal" style={{ left: `${pos(0)}%` }}>
          <span className="node-dot" />
          <span className="node-label">
            <strong>Day 0</strong>
            Perigee signal fired
            <small>{data.signal_date}</small>
          </span>
        </div>
        {data.filings.map((f) => (
          <div
            key={f.form_type + f.filed_at}
            className="timeline-node filing"
            style={{ left: `${pos(dayOf(f.filed_at))}%` }}
          >
            <span className="node-dot" />
            <span className="node-label">
              <strong>Day {dayOf(f.filed_at)}</strong>
              <a href={f.url} target="_blank" rel="noreferrer">
                {f.form_type} filed ↗
              </a>
              <small>{f.filed_at}</small>
            </span>
          </div>
        ))}
      </div>

      <ul className="filing-list">
        {data.filings.map((f) => (
          <li key={f.form_type + f.filed_at}>
            <a href={f.url} target="_blank" rel="noreferrer">
              {f.form_type}
            </a>{' '}
            — {f.description}
          </li>
        ))}
      </ul>
    </div>
  )
}
