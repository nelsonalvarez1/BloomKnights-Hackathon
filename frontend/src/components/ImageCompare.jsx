import { useState } from 'react'

// Renders one satellite snapshot with YOLO bounding boxes overlaid.
// Falls back to a styled placeholder until real NAIP images land in
// frontend/public/samples/.
function Snapshot({ snap, label }) {
  const [imgOk, setImgOk] = useState(true)

  return (
    <figure className="snapshot">
      <div className="snapshot-frame">
        {imgOk ? (
          <img
            src={snap.image_url}
            alt={`Satellite ${label}`}
            onError={() => setImgOk(false)}
          />
        ) : (
          <div className="snapshot-placeholder">
            <span>NAIP imagery pending</span>
            <code>{snap.image_url}</code>
          </div>
        )}
        {snap.boxes.map((b, i) => (
          <div
            key={i}
            className="bbox"
            title={`${b.label} ${(b.confidence * 100).toFixed(0)}%`}
            style={{
              left: `${b.x * 100}%`,
              top: `${b.y * 100}%`,
              width: `${b.w * 100}%`,
              height: `${b.h * 100}%`,
            }}
          />
        ))}
      </div>
      <figcaption>
        <span className="snapshot-label">{label}</span>
        <span className="snapshot-date">{snap.captured_at}</span>
        <span className="snapshot-count">{snap.vehicle_count} vehicles</span>
      </figcaption>
    </figure>
  )
}

export default function ImageCompare({ data }) {
  if (!data) return <div className="panel-empty">Loading satellite…</div>

  const up = data.delta_pct >= 0
  return (
    <div className="image-compare">
      <div className="compare-grid">
        <Snapshot snap={data.before} label="Before" />
        <Snapshot snap={data.after} label="After" />
      </div>
      <div className={`delta-badge ${up ? 'delta-up' : 'delta-down'}`}>
        {up ? '▲' : '▼'} {Math.abs(data.delta_pct).toFixed(1)}% lot occupancy
      </div>
    </div>
  )
}
