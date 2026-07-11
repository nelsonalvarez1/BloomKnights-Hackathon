import { useEffect, useState } from 'react'
import './App.css'
import {
  fetchEdgar,
  fetchJets,
  fetchSatellite,
  fetchStores,
  fetchTrends,
} from './api'
import EdgarTimeline from './components/EdgarTimeline'
import ImageCompare from './components/ImageCompare'
import JetMap from './components/JetMap'
import Narrative from './components/Narrative'
import PaywallModal from './components/PaywallModal'
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
  const [jets, setJets] = useState(null)
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
    setJets(null)
    setEdgar(null)
    fetchSatellite(storeId).then(setSatellite).catch(() => {})
    fetchTrends(storeId).then(setTrends).catch(() => {})
    fetchJets(storeId).then(setJets).catch(() => {})
    fetchEdgar(storeId).then(setEdgar).catch(() => {})
  }, [storeId])

  const store = stores.find((s) => s.id === storeId)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◉</span>
          <span className="brand-name">PERIGEE</span>
          <span className="brand-tag">alt-data terminal</span>
        </div>

        <div className="topbar-controls">
          <label className="store-select">
            <span>Store</span>
            <select
              value={storeId ?? ''}
              onChange={(e) => setStoreId(Number(e.target.value))}
              disabled={!stores.length}
            >
              {!stores.length && <option value="">Loading…</option>}
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} — {s.city}, {s.state} ({s.ticker})
                </option>
              ))}
            </select>
          </label>
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

      {store && (
        <div className="store-strip">
          <span className="store-strip-name">{store.company}</span>
          <span className="store-strip-detail">
            {store.name} · {store.city}, {store.state} · CIK {store.cik}
          </span>
        </div>
      )}

      <main className="grid">
        <Panel title="Satellite" tag="NAIP · YOLOv8" className="span-7">
          <ImageCompare data={satellite} />
        </Panel>
        <Panel title="Search Trends" tag="Google Trends" className="span-5">
          <TrendsChart data={trends} />
        </Panel>
        <Panel title="Corporate Jets" tag="OpenSky ADS-B" className="span-5">
          <JetMap data={jets} store={store} />
        </Panel>
        <Panel title="Signal Report" tag="Gemini" className="span-7">
          <Narrative key={storeId} storeId={storeId} />
        </Panel>
        <Panel title="EDGAR Validation" tag="SEC · data.sec.gov" className="span-12 panel-edgar">
          <EdgarTimeline data={edgar} />
        </Panel>
      </main>

      <footer className="footer">
        All signals from public sources: USGS NAIP · Google Trends · OpenSky
        Network · SEC EDGAR
      </footer>

      <PaywallModal open={paywallOpen} onClose={() => setPaywallOpen(false)} />
    </div>
  )
}
