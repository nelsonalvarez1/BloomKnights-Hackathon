import { useEffect, useMemo, useState } from 'react'
import './App.css'
import {
  fetchEdgar,
  fetchImports,
  // fetchJets, // planes section disabled for now — see JetMap below
  fetchPrice,
  fetchSatellite,
  fetchStores,
  fetchSupply,
  fetchTrends,
} from './api'
import { computeFusion } from './fusion'
import EdgarTimeline from './components/EdgarTimeline'
import FusionCommand from './components/FusionCommand'
import ImageCompare from './components/ImageCompare'
// import JetMap from './components/JetMap' // planes section disabled for now
import MetricGrid from './components/MetricGrid'
import Narrative from './components/Narrative'
import PaywallModal from './components/PaywallModal'
import SignalCascade from './components/SignalCascade'
import StoreFleet from './components/StoreFleet'
import SupplyChain from './components/SupplyChain'
import TrendsChart from './components/TrendsChart'

function Panel({ title, tag, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-header">
        <h2>{title}</h2>
        {tag && <span className="panel-tag">{tag}</span>}
      </header>
      {children}
    </section>
  )
}

export default function App() {
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState(null)
  const [satellite, setSatellite] = useState(null)
  const [trends, setTrends] = useState(null)
  // const [jets, setJets] = useState(null) // planes section disabled for now
  const [supply, setSupply] = useState(null)
  const [imports, setImports] = useState(null)
  const [price, setPrice] = useState(null)
  const [edgar, setEdgar] = useState(null)
  const [paywallOpen, setPaywallOpen] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    fetchStores()
      .then((s) => {
        setStores(s)
        if (s.length) setStoreId(s[0].id)
      })
      .catch(() => setLoadError('Cannot reach the backend — is uvicorn running on :8000?'))
  }, [])

  useEffect(() => {
    if (storeId == null) return
    setSatellite(null)
    setTrends(null)
    // setJets(null) // planes section disabled for now
    setSupply(null)
    setImports(null)
    setPrice(null)
    setEdgar(null)
    fetchSatellite(storeId).then(setSatellite).catch(() => {})
    fetchTrends(storeId).then(setTrends).catch(() => {})
    // fetchJets(storeId).then(setJets).catch(() => {}) // planes section disabled for now
    fetchSupply(storeId).then(setSupply).catch(() => {})
    fetchImports(storeId).then(setImports).catch(() => {})
    fetchPrice(storeId).then(setPrice).catch(() => {})
    fetchEdgar(storeId).then(setEdgar).catch(() => {})
  }, [storeId])

  const store = stores.find((s) => s.id === storeId)

  // The fusion engine recomputes whenever any signal lands. Ready once the
  // store is known — degrades gracefully as individual signals arrive.
  const fusion = useMemo(() => {
    if (!store) return null
    return computeFusion({ store, satellite, trends, supply, imports, edgar, price })
  }, [store, satellite, trends, supply, imports, edgar, price])

  return (
    <div className="app">
      <header className="topbar">
        <img className="logo-slot" src="/KaleidoscopeWordmarkWhite_1.png" alt="Kaleidoscope" />
        <div className="topbar-right">
          <span className="live-chip">Signals Live</span>
          <button
            type="button"
            className="upgrade-btn"
            onClick={() => setPaywallOpen(true)}
          >
            Upgrade
          </button>
        </div>
      </header>

      {loadError && <div className="load-error">{loadError}</div>}

      <div className="company-row">
        <div className="company-name">
          {store ? (
            <>
              <span className="company-label">{store.company}</span>
              <span className="company-ticker">${store.ticker}</span>
            </>
          ) : (
            <span className="company-label">Loading…</span>
          )}
        </div>
        <select
          className="store-select"
          value={storeId ?? ''}
          onChange={(e) => setStoreId(Number(e.target.value))}
          disabled={!stores.length}
          aria-label="Store"
        >
          {!stores.length && <option value="">Loading…</option>}
          {stores.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} — {s.city}, {s.state}
            </option>
          ))}
        </select>
      </div>

      <main className="grid">
        <Panel title="Fusion Command" tag="Investment Signal" className="span-12 panel-hero">
          <FusionCommand fusion={fusion} store={store} />
        </Panel>

        <Panel title="Signal Fusion Hierarchy" tag="Cross-signal graph" className="span-5">
          <SignalCascade fusion={fusion} />
        </Panel>

        <Panel title="Fleet Intelligence" tag="10 monitored sites" className="span-7">
          <StoreFleet fusion={fusion} />
        </Panel>

        <Panel title="Quant Metrics" tag="Derived signals" className="span-12">
          <MetricGrid fusion={fusion} />
        </Panel>

        <Panel title="Satellites" tag="NAIP" className="span-12">
          <ImageCompare data={satellite} />
        </Panel>

        <Panel title="EDGAR Timeline" tag="SEC" className="span-12">
          <EdgarTimeline data={edgar} />
        </Panel>

        <Panel title="Trends" tag="Google Trends" className="span-6">
          <TrendsChart data={trends} />
        </Panel>

        <Panel title="Supply Chain" tag="Port data" className="span-6">
          <SupplyChain data={supply} />
        </Panel>

        {/* Planes section disabled for now — re-enable by uncommenting this
            panel plus the JetMap import, jets state, and fetchJets call above.
        <Panel title="Corporate Jets" tag="OpenSky ADS-B" className="span-6">
          <JetMap data={jets} store={store} />
        </Panel>
        */}

        <Panel title="Signal Report" tag="Gemini" className="span-12">
          <Narrative key={storeId} storeId={storeId} />
        </Panel>
      </main>

      <footer className="footer">
        Kaleidoscope · all signals from public sources: US Customs manifests ·
        USGS NAIP imagery · Google Trends · port arrivals · SEC EDGAR
      </footer>

      <PaywallModal open={paywallOpen} onClose={() => setPaywallOpen(false)} />
    </div>
  )
}
