import { useState, useEffect, useCallback } from 'react'
import { ReactLenis, useLenis } from 'lenis/react'
import { gsap } from './lib/gsap'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import InvestigationBoard from './components/InvestigationBoard'
import TerminalOutput from './components/TerminalOutput'
import ContradictionPanel from './components/ContradictionPanel'
import ReportView from './components/ReportView'
import ToolPanel from './components/ToolPanel'
import MagneticCursor from './components/MagneticCursor'
import ApiKeyModal from './components/ApiKeyModal'

const API_BASE = '/api'

export default function App() {
  const [query, setQuery] = useState('')
  const [investigating, setInvestigating] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const lenis = useLenis()

  // API Key management states
  const [bazaarLinkKey, setBazaarLinkKey] = useState('')
  const [firecrawlKey, setFirecrawlKey] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [serverHasKeys, setServerHasKeys] = useState(false)

  useEffect(() => {
    if (!lenis) return
    // Correct integration: stop Lenis' internal RAF and drive it via GSAP ticker
    lenis.stop()
    const update = (time) => lenis.raf(time * 1000)
    gsap.ticker.add(update)
    gsap.ticker.lagSmoothing(0)
    lenis.start()
    return () => {
      gsap.ticker.remove(update)
    }
  }, [lenis])

  // Fetch status on load to verify server-side keys or request client-side keys
  useEffect(() => {
    async function checkStatus() {
      try {
        const res = await fetch(`${API_BASE}/status`)
        if (res.ok) {
          const status = await res.json()
          if (status.has_bazaarlink && status.has_firecrawl) {
            setServerHasKeys(true)
            return
          }
        }
      } catch (e) {
        console.error('Failed to retrieve server API key status:', e)
      }

      // Check localStorage if server does not have default keys pre-configured
      const bl = localStorage.getItem('bazaarlink_key') || ''
      const fc = localStorage.getItem('firecrawl_key') || ''
      if (bl && fc) {
        setBazaarLinkKey(bl)
        setFirecrawlKey(fc)
      } else {
        setShowModal(true)
      }
    }
    checkStatus()
  }, [])

  const handleSaveKeys = ({ bazaarLink, firecrawl }) => {
    localStorage.setItem('bazaarlink_key', bazaarLink)
    localStorage.setItem('firecrawl_key', firecrawl)
    setBazaarLinkKey(bazaarLink)
    setFirecrawlKey(firecrawl)
    setShowModal(false)
    setError(null)
  }

  const handleCancelKeys = () => {
    setShowModal(false)
  }

  const handleInvestigate = useCallback(async (q) => {
    setQuery(q)
    setInvestigating(true)
    setResults(null)
    setError(null)
    try {
      const headers = { 'Content-Type': 'application/json' }
      if (bazaarLinkKey) headers['X-BazaarLink-Key'] = bazaarLinkKey
      if (firecrawlKey) headers['X-Firecrawl-Key'] = firecrawlKey

      const res = await fetch(`${API_BASE}/investigate`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ query: q }),
      })
      if (res.status === 401) {
        setShowModal(true)
        throw new Error('API keys are missing or invalid. Please configure them in setup.')
      }
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setInvestigating(false)
    }
  }, [bazaarLinkKey, firecrawlKey])

  return (
    <>
      <MagneticCursor />
      {showModal && (
        <ApiKeyModal
          initialBazaarLink={bazaarLinkKey}
          initialFirecrawl={firecrawlKey}
          onSave={handleSaveKeys}
          onCancel={serverHasKeys || (bazaarLinkKey && firecrawlKey) ? handleCancelKeys : null}
        />
      )}
      <ReactLenis root options={{ lerp: 0.1, duration: 1.0, smoothWheel: true, autoRaf: false }}>
        <Header />

        {/* Credentials Status & Config Panel */}
        <div className="container" style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
          {serverHasKeys && !bazaarLinkKey && !firecrawlKey ? (
            <span className="mono" style={{ fontSize: '0.58rem', color: 'var(--success)', letterSpacing: '0.05em' }}>
              ● USING SERVER API CREDENTIALS
            </span>
          ) : (bazaarLinkKey && firecrawlKey) ? (
            <span className="mono" style={{ fontSize: '0.58rem', color: 'var(--data)', letterSpacing: '0.05em' }}>
              ● USING LOCAL BROWSER CREDENTIALS
            </span>
          ) : (
            <span className="mono" style={{ fontSize: '0.58rem', color: 'var(--accent)', letterSpacing: '0.05em' }}>
              ▲ CREDENTIALS REQUIRED FOR DEPLOYMENT
            </span>
          )}
          <button
            className="mono"
            onClick={() => setShowModal(true)}
            style={{
              background: 'transparent',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              padding: '6px 14px',
              fontSize: '0.58rem',
              cursor: 'pointer',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--text-primary)'
              e.currentTarget.style.borderColor = 'var(--border-accent)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--text-secondary)'
              e.currentTarget.style.borderColor = 'var(--border)'
            }}
          >
            ⚙ SETUP KEYS
          </button>
          {(bazaarLinkKey || firecrawlKey) && (
            <button
              className="mono"
              onClick={() => {
                localStorage.removeItem('bazaarlink_key')
                localStorage.removeItem('firecrawl_key')
                setBazaarLinkKey('')
                setFirecrawlKey('')
                if (!serverHasKeys) {
                  setShowModal(true)
                }
              }}
              style={{
                background: 'transparent',
                border: '1px solid var(--danger-dim)',
                color: 'var(--danger)',
                padding: '6px 14px',
                fontSize: '0.58rem',
                cursor: 'pointer',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--danger-dim)'
                e.currentTarget.style.color = '#fff'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = 'var(--danger)'
              }}
            >
              CLEAR KEYS
            </button>
          )}
        </div>

        <SearchBar onInvestigate={handleInvestigate} loading={investigating} />
        {investigating && (
          <section className="section">
            <div className="container">
              <p className="mono" style={{
                color: 'var(--data)', fontSize: '0.875rem',
                animation: 'pulse 1.5s ease-in-out infinite',
              }}>
                {'>'} running investigation<span className="dots"></span>
              </p>
            </div>
          </section>
        )}
        {error && (
          <section className="section" style={{ paddingTop: 0 }}>
            <div className="container">
              <p className="mono" style={{ color: 'var(--danger)', fontSize: '0.8rem' }}>
                {'!'} {error}
              </p>
            </div>
          </section>
        )}
        {results && (
          <>
            <InvestigationBoard claims={results.claims} />
            <ContradictionPanel contradictions={results.contradictions} claims={results.claims} />
            <ReportView claims={results.claims} contradictions={results.contradictions} query={query} report={results.report} reportConfidence={results.report_confidence} />
            <ToolPanel sources={results.sources} />
          </>
        )}
        {!results && !investigating && !error && (
          <footer className="section" style={{ paddingTop: 0 }}>
            <div className="container">
              <p style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.9rem' }}>
                Enter an entity, person, or organization to begin.
              </p>
            </div>
          </footer>
        )}
      </ReactLenis>
    </>
  )
}
