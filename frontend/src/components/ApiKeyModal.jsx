import { useState } from 'react'

export default function ApiKeyModal({ onSave, onCancel, initialBazaarLink = '', initialFirecrawl = '' }) {
  const [bazaarLink, setBazaarLink] = useState(initialBazaarLink)
  const [firecrawl, setFirecrawl] = useState(initialFirecrawl)
  const [showBazaarLink, setShowBazaarLink] = useState(false)
  const [showFirecrawl, setShowFirecrawl] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!bazaarLink.trim()) {
      setError('BazaarLink API Key is required.')
      return
    }
    if (!firecrawl.trim()) {
      setError('Firecrawl API Key is required.')
      return
    }
    if (!bazaarLink.startsWith('sk-')) {
      setError('BazaarLink key should start with "sk-".')
      return
    }
    if (!firecrawl.startsWith('fc-')) {
      setError('Firecrawl key should start with "fc-".')
      return
    }
    
    setError('')
    onSave({ bazaarLink: bazaarLink.trim(), firecrawl: firecrawl.trim() })
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(5, 5, 6, 0.85)',
      backdropFilter: 'blur(16px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: 20,
    }}>
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-accent)',
        padding: '32px 28px',
        width: '100%',
        maxWidth: 440,
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
      }}>
        <h2 className="mono" style={{
          fontSize: '0.95rem',
          letterSpacing: '0.12em',
          color: 'var(--accent)',
          marginBottom: 12,
          textTransform: 'uppercase',
          textAlign: 'center'
        }}>
          {'/*'} INITIALIZATION REQUIRED {'*/'}
        </h2>
        
        <p style={{
          fontFamily: 'var(--font-body)',
          fontSize: '0.85rem',
          color: 'var(--text-secondary)',
          textAlign: 'center',
          lineHeight: 1.6,
          marginBottom: 24,
        }}>
          Please enter your API credentials to access the OSINT investigation board.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          
          {/* BazaarLink Key Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label className="mono" style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
              BAZAARLINK API KEY (e.g. sk-bl-...)
            </label>
            <div style={{ position: 'relative', display: 'flex' }}>
              <input
                type={showBazaarLink ? 'text' : 'password'}
                value={bazaarLink}
                onChange={(e) => setBazaarLink(e.target.value)}
                placeholder="sk-bl-..."
                className="mono"
                style={{
                  width: '100%',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                  padding: '10px 42px 10px 12px',
                  fontSize: '0.75rem',
                  outline: 'none',
                }}
              />
              <button
                type="button"
                onClick={() => setShowBazaarLink(!showBazaarLink)}
                className="mono"
                style={{
                  position: 'absolute',
                  right: 8, top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  fontSize: '0.55rem',
                  cursor: 'pointer',
                  padding: '4px 6px',
                }}
              >
                {showBazaarLink ? 'HIDE' : 'SHOW'}
              </button>
            </div>
          </div>

          {/* Firecrawl Key Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label className="mono" style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
              FIRECRAWL API KEY (e.g. fc-...)
            </label>
            <div style={{ position: 'relative', display: 'flex' }}>
              <input
                type={showFirecrawl ? 'text' : 'password'}
                value={firecrawl}
                onChange={(e) => setFirecrawl(e.target.value)}
                placeholder="fc-..."
                className="mono"
                style={{
                  width: '100%',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                  padding: '10px 42px 10px 12px',
                  fontSize: '0.75rem',
                  outline: 'none',
                }}
              />
              <button
                type="button"
                onClick={() => setShowFirecrawl(!showFirecrawl)}
                className="mono"
                style={{
                  position: 'absolute',
                  right: 8, top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  fontSize: '0.55rem',
                  cursor: 'pointer',
                  padding: '4px 6px',
                }}
              >
                {showFirecrawl ? 'HIDE' : 'SHOW'}
              </button>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <p className="mono" style={{ fontSize: '0.65rem', color: 'var(--danger)', margin: 0, textAlign: 'center' }}>
              ⚠ {error}
            </p>
          )}

          {/* Info text */}
          <p className="mono" style={{ fontSize: '0.55rem', color: 'var(--text-muted)', lineHeight: 1.5, textAlign: 'center', margin: 0 }}>
            * Stored locally in your browser's localStorage. Never sent to any third party other than direct API endpoints.
          </p>

          {/* Submit/Cancel Area */}
          <div style={{ display: 'flex', gap: 12, marginTop: 10 }}>
            {onCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="mono"
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: '1px solid var(--border)',
                  color: 'var(--text-secondary)',
                  padding: '12px 0',
                  fontWeight: 700,
                  fontSize: '0.72rem',
                  letterSpacing: '0.1em',
                  cursor: 'pointer',
                }}
              >
                CANCEL
              </button>
            )}
            <button
              type="submit"
              className="mono"
              style={{
                flex: 1,
                background: 'var(--accent)',
                border: 'none',
                color: 'var(--bg-primary)',
                padding: '12px 0',
                fontWeight: 700,
                fontSize: '0.72rem',
                letterSpacing: '0.1em',
                cursor: 'pointer',
                transition: 'opacity 0.2s ease',
              }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '0.85'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
            >
              SAVE & LAUNCH
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
