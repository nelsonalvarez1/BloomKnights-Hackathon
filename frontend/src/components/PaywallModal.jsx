const TIERS = [
  {
    name: 'Watcher',
    price: 'Free',
    features: ['1 tracked store', 'Weekly trends refresh', 'EDGAR timeline (delayed)'],
    cta: 'Current plan',
    current: true,
  },
  {
    name: 'Analyst',
    price: '$29/mo',
    features: [
      '25 tracked stores',
      'Daily satellite + trends refresh',
      'Jet proximity alerts',
      'Gemini narrative reports',
    ],
    cta: 'Upgrade',
    highlight: true,
  },
  {
    name: 'Desk',
    price: '$199/mo',
    features: [
      'Unlimited stores + watchlists',
      'API access',
      'Historical signal backtesting',
      'Priority data refresh',
    ],
    cta: 'Contact us',
  },
]

export default function PaywallModal({ open, onClose }) {
  if (!open) return null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-label="Pricing"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="modal-header">
          <h2>Institutional signals, retail price</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <p className="modal-sub">
          The same multi-signal fusion desks pay five figures for — validated
          against the filings, store by store.
        </p>
        <div className="tier-grid">
          {TIERS.map((t) => (
            <div key={t.name} className={`tier ${t.highlight ? 'tier-highlight' : ''}`}>
              <h3>{t.name}</h3>
              <div className="tier-price">{t.price}</div>
              <ul>
                {t.features.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <button type="button" className="tier-cta" disabled={t.current}>
                {t.cta}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
