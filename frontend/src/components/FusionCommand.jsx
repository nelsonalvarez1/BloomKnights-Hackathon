import { useCountUp } from '../hooks'

// The command panel — the single answer the dashboard exists to give:
// buy or not, how sure, and how much upside. Confidence ring + recommendation
// + forward price targets, all animated.

function ConfidenceRing({ pct, band, tone }) {
  const shown = useCountUp(pct, { duration: 1100 })
  const R = 66
  const C = 2 * Math.PI * R
  const off = C * (1 - pct / 100)
  return (
    <div className="conf-ring">
      <svg viewBox="0 0 160 160" width="160" height="160">
        <circle cx="80" cy="80" r={R} className="ring-track" />
        <circle
          cx="80" cy="80" r={R}
          className={`ring-fill ring-${tone}`}
          strokeDasharray={C}
          strokeDashoffset={off}
          transform="rotate(-90 80 80)"
        />
      </svg>
      <div className="ring-center">
        <span className="ring-pct">{shown}%</span>
        <span className="ring-band">{band}</span>
        <span className="ring-sub">Confidence</span>
      </div>
    </div>
  )
}

function TargetStat({ label, value, sub, tone }) {
  const shown = useCountUp(value, { duration: 950, decimals: 2 })
  return (
    <div className="target-stat">
      <span className="target-label">{label}</span>
      <span className={`target-value tone-${tone}`}>${shown.toFixed(2)}</span>
      {sub != null && <span className="target-sub">{sub}</span>}
    </div>
  )
}

const pct1 = (x) => `${x >= 0 ? '+' : ''}${(x * 100).toFixed(1)}%`

export default function FusionCommand({ fusion, store }) {
  // Hooks must run unconditionally and in stable order — read with safe
  // fallbacks first, then bail to the loading state below.
  const conviction = fusion?.conviction ?? 0
  const horizons = fusion?.horizons ?? { d7: 0, d30: 0, d90: 0 }
  const convShown = useCountUp(Math.abs(conviction) * 100, { duration: 900 })
  const retShown = useCountUp(horizons.d90 * 100, { duration: 950, decimals: 1 })

  if (!fusion) return <div className="panel-empty">Fusing signals…</div>
  const { recommendation: rec, confidence, price, revenue, agg } = fusion

  return (
    <div className="fusion-command">
      <div className="fc-verdict">
        <div className={`rec-badge rec-${rec.tone}`}>
          <span className="rec-label">{rec.label}</span>
          <span className="rec-ticker">${store?.ticker}</span>
        </div>
        <p className="fc-headline">
          Kaleidoscope fuses {fusion.cascade.length} signal layers across{' '}
          {agg.coverage} monitored sites into one conviction read.
        </p>
        <div className="conviction-bar">
          <div className="cb-scale">
            <span>AVOID</span><span>HOLD</span><span>STRONG BUY</span>
          </div>
          <div className="cb-track">
            <div className="cb-mid" />
            <div
              className={`cb-marker rec-${rec.tone}`}
              style={{ left: `${clampPct(50 + conviction * 50)}%` }}
            />
          </div>
          <span className="cb-value">Market Conviction {Math.round(convShown)}%</span>
        </div>
      </div>

      <ConfidenceRing pct={confidence.pct} band={confidence.band} tone={rec.tone} />

      <div className="fc-targets">
        <div className="target-stat">
          <span className="target-label">
            Current
            {price.source === 'live' && <span className="live-chip live-inline">Live</span>}
          </span>
          <span className="target-value tone-neutral">${price.current.toFixed(2)}</span>
          {price.dayChange != null && (
            <span className={`target-sub tone-${tone(price.dayChange)}`}>
              {price.dayChange >= 0 ? '+' : ''}{price.dayChange.toFixed(2)}% today
            </span>
          )}
        </div>
        <TargetStat
          label="30-Day Target" value={price.target30} tone={rec.tone}
          sub={pct1(horizons.d30)}
        />
        <TargetStat label="Fair Value" value={price.fairValue} tone={rec.tone} />
        <div className="target-stat">
          <span className="target-label">Expected 90-Day Return</span>
          <span className={`target-value tone-${rec.tone}`}>
            {retShown >= 0 ? '+' : ''}{retShown.toFixed(1)}%
          </span>
          <span className="target-sub">
            bull ${price.bull.toFixed(0)} · bear ${price.bear.toFixed(0)}
          </span>
        </div>
      </div>

      <div className="fc-strip">
        <Chip k="Est. Quarterly Rev" v={fmtMoney(revenue.quarterly)} />
        <Chip k="Revenue Momentum" v={pct1(revenue.lift)} tone={tone(revenue.lift)} />
        <Chip k="EPS Surprise" v={pct1(revenue.epsSurprise)} tone={tone(revenue.epsSurprise)} />
        <Chip k="Signal Consensus" v={`${Math.round(confidence.agreement * 100)}%`} tone="pos" />
      </div>
    </div>
  )
}

function Chip({ k, v, tone = 'neutral' }) {
  return (
    <div className="fc-chip">
      <span className="fc-chip-k">{k}</span>
      <span className={`fc-chip-v tone-${tone}`}>{v}</span>
    </div>
  )
}

const tone = (x) => (x > 0 ? 'pos' : x < 0 ? 'neg' : 'neutral')
const clampPct = (x) => Math.max(3, Math.min(97, x))
const fmtMoney = (x) =>
  x >= 1e9 ? `$${(x / 1e9).toFixed(2)}B` : x >= 1e6 ? `$${(x / 1e6).toFixed(1)}M` : `$${Math.round(x)}`
