import { useState } from 'react'
import { generateNarrative } from '../api'

// Gemini output display. "Generate Report" pulls the fused payload through
// /api/narrative; the backend falls back to a template thesis if no Gemini
// key is configured, so this always renders something.

export default function Narrative({ storeId }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function onGenerate() {
    setLoading(true)
    setError(null)
    try {
      setReport(await generateNarrative(storeId))
    } catch {
      setError('Report generation failed — is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="narrative">
      <button
        type="button"
        className="generate-btn"
        onClick={onGenerate}
        disabled={loading || storeId == null}
      >
        {loading ? 'Synthesizing signals…' : 'Generate Report'}
      </button>

      {error && <p className="narrative-error">{error}</p>}

      {report && (
        <article className="narrative-body">
          <header>
            <span className={`confidence confidence-${report.confidence}`}>
              {report.confidence} confidence
            </span>
            <span className="narrative-sources">
              cites: {report.sources.join(' · ')}
            </span>
          </header>
          {report.thesis.split('\n\n').map((para, i) => (
            <p key={i}>{para}</p>
          ))}
        </article>
      )}

      {!report && !loading && !error && (
        <p className="narrative-hint">
          Fuses satellite, search trends, jet activity, and the EDGAR timeline
          into a written thesis with receipts.
        </p>
      )}
    </div>
  )
}
