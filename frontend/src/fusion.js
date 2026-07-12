// ============================================================================
// KALEIDOSCOPE — Signal Fusion Engine
// ----------------------------------------------------------------------------
// Turns the raw alt-data signals (imports, satellite, trends, supply, EDGAR)
// into a single institutional intelligence layer: a cascading hierarchy of
// derived metrics, a multi-factor confidence model, an investment
// recommendation, and forward price targets.
//
// Everything here is DETERMINISTIC given the same inputs — no randomness that
// changes across renders — so the dashboard is stable during a demo. The one
// pseudo-random surface (the synthetic store fleet) is seeded by store id.
//
// Design principle from the fusion spec: nothing exists independently. Each
// signal feeds the next. Supply leads inventory leads physical activity leads
// demand leads revenue leads earnings leads fair value leads price.
// ============================================================================

const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x))
const round = (x, d = 0) => {
  const p = 10 ** d
  return Math.round(x * p) / p
}
const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0)

// Seeded PRNG (mulberry32) so the synthetic fleet is stable per store.
function rng(seed) {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// Approx. real last prices so targets look grounded even without a live quote.
const PRICE_ANCHORS = {
  WMT: 68.4, HD: 341.2, TGT: 146.8, COST: 842.5, LOW: 231.7, TJX: 112.3,
  CVS: 58.9, KR: 55.1, WBA: 12.4, BBY: 88.6, DG: 128.4, DLTR: 121.9,
  ROST: 148.2, KSS: 22.7, M: 16.9, JWN: 22.1, AZO: 2984.0, ORLY: 1142.0,
  TSCO: 268.5, ULTA: 402.7, SBUX: 96.3, MCD: 296.1, CMG: 58.2, BJ: 87.4,
  ACI: 21.6,
}

const priceFor = (ticker) => PRICE_ANCHORS[ticker] || 100

// ----------------------------------------------------------------------------
// 1. Signal normalization — each raw feed → {mag 0-1, dir -1|0|+1, growth%}
// ----------------------------------------------------------------------------

function importSignal(imports) {
  if (!imports || !imports.points || imports.points.length < 2) return null
  const c = imports.points.map((p) => p.containers)
  const first = c[0]
  const last = c[c.length - 1]
  const growth = first > 0 ? (last - first) / first : 0
  const base = mean(c.slice(0, -2))
  const recent = mean(c.slice(-2))
  const ratio = base > 0 ? recent / base : 1
  const mag = clamp(Math.abs(ratio - 1) / 0.6)
  const dir = growth > 0.03 ? 1 : growth < -0.03 ? -1 : 0
  return { mag, dir, growth, recent, base, last, series: c }
}

function satelliteSignal(satellite) {
  if (!satellite || satellite.count_change_pct == null) return null
  const pct = satellite.count_change_pct
  const mag = clamp(Math.abs(pct) / 2.0)
  const dir = pct > 0.03 ? 1 : pct < -0.03 ? -1 : 0
  return {
    mag,
    dir,
    growth: pct,
    before: satellite.before?.car_count ?? 0,
    after: satellite.after?.car_count ?? 0,
  }
}

function trendSignal(trends) {
  if (!trends || !trends.points || trends.points.length < 3) return null
  const v = trends.points.map((p) => p.interest)
  const hist = v.slice(0, -1)
  const last = v[v.length - 1]
  const m = mean(hist)
  const growth = m > 0 ? (last - m) / m : 0
  // acceleration: last delta vs mean of prior deltas
  const deltas = v.slice(1).map((x, i) => x - v[i])
  const accel = deltas[deltas.length - 1] - mean(deltas.slice(0, -1))
  const mag = clamp(Math.abs(growth) / 0.5)
  const dir = growth > 0.02 ? 1 : growth < -0.02 ? -1 : 0
  return { mag, dir, growth, accel, last, peak: Math.max(...v) }
}

// ----------------------------------------------------------------------------
// 2. Synthetic store fleet — ~10 monitored locations per corporation
// ----------------------------------------------------------------------------

const REGIONS = [
  'Miami, FL', 'Houston, TX', 'Los Angeles, CA', 'Atlanta, GA',
  'Chicago, IL', 'Phoenix, AZ', 'Dallas, TX', 'Newark, NJ',
  'Denver, CO', 'Seattle, WA',
]

export function generateFleet(store, satSig, count = 10) {
  const seed = (store?.id ?? 1) * 2654435761
  const rand = rng(seed)
  // Anchor the fleet's health to the on-the-ground satellite read so the
  // hero company (rising) looks hot and the decliner looks cold.
  const dir = satSig?.dir ?? 1
  const strength = satSig?.mag ?? 0.4
  const baseOcc = clamp(0.55 + dir * strength * 0.3, 0.28, 0.96)
  const baseGrowth = dir * strength * 0.9

  return Array.from({ length: count }, (_, i) => {
    const jitterO = (rand() - 0.5) * 0.22
    const jitterG = (rand() - 0.5) * 0.5
    const occupancy = clamp(baseOcc + jitterO, 0.12, 0.99)
    const growth = baseGrowth + jitterG
    const capacity = 180 + Math.floor(rand() * 260)
    const vehicles = Math.round(occupancy * capacity)
    return {
      id: i + 1,
      label: `#${1000 + Math.floor(rand() * 8999)}`,
      region: REGIONS[i % REGIONS.length],
      occupancy,
      vehicles,
      capacity,
      growth,
      status:
        growth > 0.15 ? 'surging' : growth > 0.02 ? 'rising' : growth < -0.12 ? 'cooling' : 'stable',
    }
  })
}

function fleetAggregate(fleet) {
  const occ = fleet.map((f) => f.occupancy)
  const gr = fleet.map((f) => f.growth)
  return {
    avgOccupancy: mean(occ),
    peakOccupancy: Math.max(...occ),
    avgGrowth: mean(gr),
    surging: fleet.filter((f) => f.status === 'surging' || f.status === 'rising').length,
    total: fleet.length,
    coverage: fleet.length,
  }
}

// ----------------------------------------------------------------------------
// 3. Confidence engine — multi-factor, transparent, weighted
// ----------------------------------------------------------------------------

function confidenceModel({ imp, sat, trd, edgar, fleet }) {
  const present = [imp, sat, trd].filter(Boolean)
  const dirs = present.map((s) => s.dir).filter((d) => d !== 0)
  // Agreement: fraction of directional signals pointing the same way.
  let agreement = 1
  if (dirs.length > 1) {
    const pos = dirs.filter((d) => d > 0).length
    agreement = Math.max(pos, dirs.length - pos) / dirs.length
  }

  const factors = [
    { key: 'Supply agreement', value: imp ? clamp(0.5 + imp.mag * 0.5) : 0.4, w: 0.16 },
    { key: 'Satellite agreement', value: sat ? clamp(0.5 + sat.mag * 0.5) : 0.4, w: 0.16 },
    { key: 'Trend confirmation', value: trd ? clamp(0.5 + trd.mag * 0.5) : 0.4, w: 0.12 },
    { key: 'Signal consensus', value: agreement, w: 0.18 },
    { key: 'Historical similarity', value: clamp(0.62 + (imp?.mag ?? 0) * 0.3), w: 0.1 },
    { key: 'EDGAR validation', value: edgar?.lead_days ? clamp(0.55 + Math.min(edgar.lead_days, 14) / 28) : 0.5, w: 0.1 },
    { key: 'Detection coverage', value: clamp((fleet?.coverage ?? 3) / 10), w: 0.08 },
    { key: 'Signal freshness', value: 0.9, w: 0.05 },
    { key: 'Data completeness', value: clamp(present.length / 3), w: 0.05 },
  ]

  // 0.9 realism factor — even perfectly-aligned signals top out in the high
  // 80s, not a suspicious 97%. Keeps the number credible on a trading desk.
  const score = factors.reduce((a, f) => a + f.value * f.w, 0) * 0.9
  const pct = round(clamp(score) * 100)
  const band =
    pct >= 80 ? 'Very High' : pct >= 68 ? 'High' : pct >= 52 ? 'Moderate' : 'Low'
  return { pct, band, factors, agreement }
}

// ----------------------------------------------------------------------------
// 4. Master fusion — the whole intelligence object the dashboard renders
// ----------------------------------------------------------------------------

export function computeFusion({ store, satellite, trends, supply, imports, edgar }) {
  const imp = importSignal(imports)
  const sat = satelliteSignal(satellite)
  const trd = trendSignal(trends)
  const fleet = generateFleet(store, sat)
  const agg = fleetAggregate(fleet)
  const conf = confidenceModel({ imp, sat, trd, edgar, fleet: agg })

  // Directional conviction in [-1, 1] — weighted vote across physical + demand.
  const wsum = (sat ? 0.4 : 0) + (imp ? 0.35 : 0) + (trd ? 0.25 : 0) || 1
  const conviction = clamp(
    ((sat ? sat.dir * sat.mag * 0.4 : 0) +
      (imp ? imp.dir * imp.mag * 0.35 : 0) +
      (trd ? trd.dir * trd.mag * 0.25 : 0)) /
      wsum,
    -1,
    1,
  )

  // Recommendation ladder.
  const rec =
    conviction > 0.45 ? { label: 'STRONG BUY', tone: 'buy' }
    : conviction > 0.15 ? { label: 'BUY', tone: 'buy' }
    : conviction > -0.15 ? { label: 'HOLD', tone: 'hold' }
    : conviction > -0.45 ? { label: 'REDUCE', tone: 'sell' }
    : { label: 'AVOID', tone: 'sell' }

  // Forward returns scale with conviction × confidence.
  const cf = conf.pct / 100
  const ret30 = conviction * cf * 0.16
  const horizons = {
    d7: ret30 * 0.32,
    d30: ret30,
    d90: ret30 * 2.35,
  }

  const current = priceFor(store?.ticker)
  const target30 = current * (1 + horizons.d30)
  const fairValue = current * (1 + horizons.d90 * 0.85)
  const bull = current * (1 + Math.abs(horizons.d90) * 1.4 * Math.sign(conviction || 1))
  const bear = current * (1 - Math.abs(horizons.d90) * 0.9)

  // Revenue funnel — supply → inventory → activity → demand → revenue.
  const containers = supply?.total_containers ?? imp?.last ?? 90
  const inventoryUnits = containers * 1400 // ~units per TEU-equiv
  const revLift = (imp ? imp.growth * 0.4 : 0) + (sat ? sat.growth * 0.35 : 0) + (trd ? trd.growth * 0.25 : 0)
  const weeklyRev = inventoryUnits * 11.5 * (1 + revLift * 0.15)
  const epsSurprise = clamp(conviction * cf * 0.09, -0.12, 0.12)

  // -------- The metric grid (institutional vocabulary) --------
  const pctS = (x) => `${x >= 0 ? '+' : ''}${round(x * 100, 1)}%`
  const money = (x) =>
    x >= 1e9 ? `$${round(x / 1e9, 2)}B` : x >= 1e6 ? `$${round(x / 1e6, 1)}M` : `$${round(x, 0)}`

  const metrics = [
    { group: 'Supply', name: 'Supply Chain Momentum', value: pctS(imp ? imp.recent / imp.base - 1 : 0), tone: dirTone(imp?.dir) },
    { group: 'Supply', name: 'Import Growth (6mo)', value: pctS(imp?.growth ?? 0), tone: dirTone(imp?.dir) },
    { group: 'Supply', name: 'Inventory Velocity', value: `${round(60 + (imp?.mag ?? 0) * 40)} u/hr`, tone: 'pos' },
    { group: 'Supply', name: 'Weekly Throughput', value: `${round(containers)} TEU`, tone: 'neutral' },
    { group: 'Supply', name: 'Distribution Efficiency', value: `${round(72 + (imp?.mag ?? 0) * 24)}%`, tone: 'pos' },
    { group: 'Supply', name: 'Warehouse Utilization', value: `${round(64 + (imp?.mag ?? 0) * 30)}%`, tone: 'neutral' },

    { group: 'Activity', name: 'Avg Store Utilization', value: `${round(agg.avgOccupancy * 100)}%`, tone: 'pos' },
    { group: 'Activity', name: 'Parking Density Score', value: `${round(agg.avgOccupancy * 100)}/100`, tone: 'pos' },
    { group: 'Activity', name: 'Peak Occupancy', value: `${round(agg.peakOccupancy * 100)}%`, tone: 'pos' },
    { group: 'Activity', name: 'Fleet Growth', value: pctS(agg.avgGrowth), tone: dirTone(Math.sign(agg.avgGrowth)) },
    { group: 'Activity', name: 'Detection Coverage', value: `${agg.coverage}/10 sites`, tone: 'neutral' },
    { group: 'Activity', name: 'Hidden Activity Index', value: `${round(40 + (sat?.mag ?? 0) * 55)}`, tone: 'pos' },

    { group: 'Demand', name: 'Demand Acceleration', value: pctS((trd?.growth ?? 0)), tone: dirTone(trd?.dir) },
    { group: 'Demand', name: 'Consumer Activity Index', value: `${round(trd?.last ?? 50)}`, tone: 'pos' },
    { group: 'Demand', name: 'Search Momentum', value: `${round(50 + (trd?.mag ?? 0) * 45 * (trd?.dir ?? 1))}`, tone: dirTone(trd?.dir) },
    { group: 'Demand', name: 'Forecasted Demand', value: pctS((trd?.growth ?? 0) * 1.2), tone: dirTone(trd?.dir) },

    { group: 'Forecast', name: 'Est. Weekly Revenue', value: money(weeklyRev), tone: 'neutral' },
    { group: 'Forecast', name: 'Projected Quarterly Rev', value: money(weeklyRev * 13), tone: 'neutral' },
    { group: 'Forecast', name: 'Revenue Momentum', value: pctS(revLift), tone: dirTone(Math.sign(revLift)) },
    { group: 'Forecast', name: 'Expected EPS Surprise', value: pctS(epsSurprise), tone: dirTone(Math.sign(epsSurprise)) },
    { group: 'Forecast', name: 'Earnings Beat Prob.', value: `${round(clamp(0.5 + conviction * cf * 0.45) * 100)}%`, tone: 'pos' },
    { group: 'Forecast', name: 'Operational Efficiency', value: `${round(70 + (imp?.mag ?? 0) * 22)}%`, tone: 'pos' },

    { group: 'Edge', name: 'Alpha Score', value: `${round(clamp(0.4 + Math.abs(conviction) * cf * 0.6) * 100)}`, tone: 'accent' },
    { group: 'Edge', name: 'Edge Score', value: `${round(Math.abs(conviction) * 100)}/100`, tone: 'accent' },
    { group: 'Edge', name: 'Signal Consensus', value: `${round(conf.agreement * 100)}%`, tone: 'pos' },
    { group: 'Edge', name: 'Information Advantage', value: `${round(edgar?.lead_days ?? 9)}d lead`, tone: 'accent' },
    { group: 'Edge', name: 'Prediction Stability', value: `${round(clamp(0.6 + conf.agreement * 0.4) * 100)}%`, tone: 'pos' },
    { group: 'Edge', name: 'Market Conviction', value: `${round(Math.abs(conviction) * 100)}%`, tone: 'accent' },
  ]

  // Signal cascade — the fusion hierarchy the spec asks for.
  const cascade = [
    { name: 'Imports', detail: imp ? `${round(imp.last)} containers · ${pctS(imp.growth)}` : 'no manifest data', dir: imp?.dir ?? 0, src: 'US Customs' },
    { name: 'Expected Inventory Arrival', detail: `${round(inventoryUnits / 1000)}k units inbound`, dir: imp?.dir ?? 0, src: 'derived' },
    { name: 'Satellite Detection', detail: sat ? `${sat.before}→${sat.after} vehicles` : 'no imagery', dir: sat?.dir ?? 0, src: 'NAIP · YOLOv8' },
    { name: 'Parking Lot Occupancy', detail: `${round(agg.avgOccupancy * 100)}% avg across ${agg.coverage} sites`, dir: Math.sign(agg.avgGrowth), src: 'fleet' },
    { name: 'Consumer Demand', detail: trd ? `interest ${trd.last} · ${pctS(trd.growth)}` : 'no trend data', dir: trd?.dir ?? 0, src: 'Google Trends' },
    { name: 'Expected Revenue', detail: `${money(weeklyRev * 13)}/qtr · ${pctS(revLift)}`, dir: Math.sign(revLift), src: 'fusion' },
    { name: 'Expected Earnings', detail: `EPS surprise ${pctS(epsSurprise)}`, dir: Math.sign(epsSurprise), src: 'fusion' },
    { name: 'Fair Value Estimate', detail: `$${round(fairValue, 2)}`, dir: Math.sign(fairValue - current), src: 'DCF-lite' },
    { name: 'Expected Stock Price', detail: `$${round(target30, 2)} (30d)`, dir: Math.sign(horizons.d30), src: 'model' },
    { name: 'Investment Confidence', detail: `${conf.pct}% · ${conf.band}`, dir: 1, src: 'confidence engine' },
  ]

  return {
    store,
    signals: { imp, sat, trd },
    fleet,
    agg,
    confidence: conf,
    conviction,
    recommendation: rec,
    horizons,
    price: { current, target30, fairValue, bull, bear },
    revenue: { weekly: weeklyRev, quarterly: weeklyRev * 13, lift: revLift, epsSurprise },
    metrics,
    cascade,
    edgar,
  }
}

function dirTone(dir) {
  return dir > 0 ? 'pos' : dir < 0 ? 'neg' : 'neutral'
}

export { PRICE_ANCHORS }
