// The fusion hierarchy — every layer feeds the next. Renders the spec's
// signal cascade (Imports → Inventory → Satellite → … → Investment Confidence)
// as a connected vertical flow with directional arrows and live values.

const arrow = (dir) => (dir > 0 ? '▲' : dir < 0 ? '▼' : '■')
const cls = (dir) => (dir > 0 ? 'up' : dir < 0 ? 'down' : 'flat')

export default function SignalCascade({ fusion }) {
  if (!fusion) return <div className="panel-empty">Building fusion graph…</div>
  return (
    <ol className="cascade">
      {fusion.cascade.map((node, i) => (
        <li
          className="cascade-node"
          key={node.name}
          style={{ animationDelay: `${0.06 * i}s` }}
        >
          <div className="cascade-rail">
            <span className={`cascade-dot dir-${cls(node.dir)}`} />
            {i < fusion.cascade.length - 1 && <span className="cascade-line" />}
          </div>
          <div className="cascade-body">
            <div className="cascade-top">
              <span className="cascade-name">{node.name}</span>
              <span className="cascade-src">{node.src}</span>
            </div>
            <div className="cascade-detail">
              <span className={`cascade-arrow dir-${cls(node.dir)}`}>{arrow(node.dir)}</span>
              {node.detail}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}
