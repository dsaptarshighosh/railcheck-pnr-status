import { FormEvent, useEffect, useRef, useState } from 'react'
import { ArrowDownRight, ArrowRight, Check, CircleAlert, Clock3, Copy, ExternalLink, Moon, RefreshCw, Sun, TrainFront, X } from 'lucide-react'

type Passenger = { number: number; bookingStatus: string; currentStatus: string; coach?: string; berth?: string }
type Result = { train: { number: string; name: string }; journeyDate?: string; from: string; to: string; departure?: string; arrival?: string; chart?: string; updatedAt?: string; passengers: Passenger[]; mode: 'live' }

function Status({ value }: { value: string }) {
  const kind = value.startsWith('CNF') ? 'confirmed' : value.startsWith('RAC') ? 'rac' : value.includes('WL') ? 'waitlist' : 'other'
  return <span className={`status status-${kind}`}><i />{value}</span>
}

export default function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const savedTheme = window.localStorage.getItem('railcheck-theme')
    if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })
  const [pnr, setPnr] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const [lastChecked, setLastChecked] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [legalModal, setLegalModal] = useState<'terms' | 'privacy' | null>(null)
  const legalDialogRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('railcheck-theme', theme)
  }, [theme])

  useEffect(() => {
    if (!legalModal) return
    const previousFocus = document.activeElement as HTMLElement | null
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setLegalModal(null)
    }
    window.addEventListener('keydown', closeOnEscape)
    legalDialogRef.current?.querySelector<HTMLButtonElement>('.modal-close')?.focus()
    return () => {
      window.removeEventListener('keydown', closeOnEscape)
      previousFocus?.focus()
    }
  }, [legalModal])

  async function lookup(event: FormEvent) {
    event.preventDefault()
    setResult(null); setError(''); setLastChecked('')
    if (!/^\d{10}$/.test(pnr)) { setError('Enter a valid 10-digit PNR number.'); return }
    setBusy(true)
    try {
      const response = await fetch('/api/pnr', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pnr }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'We could not retrieve this PNR. Please try again.')
      setResult(payload); setLastChecked(new Date().toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }))
    } catch (e) { setError(e instanceof Error ? e.message : 'The service could not be reached. Check your connection and try again.') }
    finally { setBusy(false) }
  }

  async function copyPnr() {
    await navigator.clipboard.writeText(pnr); setCopied(true); window.setTimeout(() => setCopied(false), 1600)
  }

  return <div className="app-shell">
    <header className="topbar">
      <a href="#top" className="brand" aria-label="RailCheck home"><span className="brand-mark"><TrainFront size={19} strokeWidth={2.1} /></span><span>Rail<span>Check</span></span></a>
      <nav className={menuOpen ? 'nav nav-open' : 'nav'} aria-label="Main navigation"><a href="#lookup" onClick={() => setMenuOpen(false)}>PNR status</a><a href="#about" onClick={() => setMenuOpen(false)}>About</a></nav>
      <button className="theme-toggle" type="button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>{theme === 'dark' ? <Sun size={17}/> : <Moon size={17}/>}<span>{theme === 'dark' ? 'Light' : 'Dark'}</span></button>
      <button className="menu-toggle" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen} aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}>{menuOpen ? <X size={20}/> : <span>Menu</span>}</button>
      <a className="header-action" href="#lookup">Check a PNR <ArrowDownRight size={15}/></a>
    </header>

    <main id="top">
      <section className="hero" id="lookup">
        <div className="hero-copy"><h1>Check your train<br className="desktop-break"/> PNR status.</h1><p>See the latest reservation details available for your trip.</p></div>
        <div className="lookup-stage">
          <div className="stage-top"><span>RESERVATION STATUS</span><span className="stage-index">10 digits</span></div>
          <form className="lookup-form" onSubmit={lookup} noValidate>
            <label htmlFor="pnr">Enter your 10-digit PNR number</label>
            <div className="input-row"><input id="pnr" name="pnr" type="text" inputMode="numeric" autoComplete="off" maxLength={10} pattern="[0-9]{10}" placeholder="e.g. 4123456789" value={pnr} onChange={e => {setPnr(e.target.value.replace(/\D/g, '').slice(0,10)); if (error) setError('')}} aria-describedby="pnr-help pnr-error"/><button type="submit" disabled={busy}>{busy ? <><span className="spinner"/> Checking</> : <>Check status <ArrowRight size={17}/></>}</button></div>
            <div className="field-meta"><span id="pnr-help">10 digits, found on your ticket or booking confirmation</span><span>{pnr.length}/10</span></div>
            {error && <p className="form-error" id="pnr-error" role="alert"><CircleAlert size={16}/>{error}</p>}
            {busy && <p className="loading-note" role="status"><span className="spinner dark"/> Connecting to the configured enquiry service…</p>}
          </form>
          <div className="privacy-note"><span className="privacy-icon" aria-hidden="true">i</span><span>Lookup requests are processed by API Mitra. <a href="#privacy" onClick={event => { event.preventDefault(); setLegalModal('privacy') }}>Privacy details</a></span></div>
        </div>
        <div className="hero-foot"><span>Independent passenger tool</span><span>Not affiliated with Indian Railways or IRCTC</span></div>
      </section>

      {result && <section className="results-wrap" aria-live="polite">
        <article className="result-panel">
          <div className="result-heading"><div><h2>{result.train.name}</h2><p className="train-number">Train {result.train.number}{result.journeyDate && <> <span>·</span> Journey date {result.journeyDate}</>}</p></div><div className="result-actions"><button onClick={copyPnr} title="Copy entered PNR" aria-label="Copy entered PNR">{copied ? <Check size={16}/> : <Copy size={16}/>}<span>{copied ? 'Copied' : 'Copy PNR'}</span></button><button onClick={() => lookup({ preventDefault() {} } as FormEvent)} title="Refresh status" aria-label="Refresh status"><RefreshCw size={16}/><span>Refresh</span></button></div></div>
          <div className="route"><div className="station"><strong>{result.from}</strong><span>{result.departure ? `Departure ${result.departure}` : 'Departure unavailable'}</span></div><div className="route-line"><span><TrainFront size={16}/></span></div><div className="station station-end"><strong>{result.to}</strong><span>{result.arrival ? `Arrival ${result.arrival}` : 'Arrival unavailable'}</span></div></div>
          <div className="passenger-table"><div className="table-head"><span>PASSENGER</span><span>BOOKING STATUS</span><span>CURRENT STATUS</span><span>COACH / BERTH</span></div>{result.passengers.map(p => <div className="passenger-row" key={p.number}><span className="passenger-name">Passenger {p.number}</span><span className="status-cell" role="group" aria-label="Booking status" data-label="Booking status"><Status value={p.bookingStatus}/></span><span className="status-cell" role="group" aria-label="Current status" data-label="Current status"><Status value={p.currentStatus}/></span><span className="berth" role="group" aria-label="Coach or berth" data-label="Coach / berth">{p.coach && p.berth ? `${p.coach} · ${p.berth}` : 'Not allotted'}</span></div>)}</div>
          <div className="result-bottom"><div className="explanation"><strong>{result.passengers[0]?.currentStatus.startsWith('RAC') ? 'Reservation Against Cancellation' : result.passengers[0]?.currentStatus.startsWith('CNF') ? 'Reservation confirmed' : result.passengers[0]?.currentStatus.includes('WL') ? 'Waitlisted reservation' : 'Status returned by provider'}</strong><p>{result.passengers[0]?.currentStatus.startsWith('RAC') ? 'Travel eligibility and accommodation depend on applicable railway rules.' : result.passengers[0]?.currentStatus.startsWith('CNF') ? 'Coach and berth details appear only when supplied by the provider.' : result.passengers[0]?.currentStatus.includes('WL') ? 'Boarding eligibility depends on ticket type and applicable railway rules.' : 'Check the status details against the official railway enquiry service.'}</p></div><div className="result-meta"><span><Clock3 size={14}/> Chart: {result.chart || 'Not available'}</span><span>Last checked {lastChecked || 'Not available'}</span>{result.updatedAt && <span>Provider update {result.updatedAt}</span>}</div></div>
        </article>
      </section>}

      {!result && <section className="empty-state" aria-label="PNR status information"><div className="empty-graphic"><div className="ticket-notch"/><div className="ticket-row"><span>PNR STATUS</span><span className="ticket-dots">••••••</span><span className="ticket-line"/><span className="ticket-status"><i/> Awaiting lookup</span></div><div className="ticket-rail"/></div><div className="empty-copy"><h2>Your journey,<br/>at a glance.</h2><p>Enter a PNR above to see booking and current status side by side, along with the journey details the provider makes available.</p></div></section>}

      <section className="how-section" id="about"><div className="how-title"><h2>One number.<br/>The details that matter.</h2></div><div className="how-points"><div className="how-point"><div><h3>Separate status, clearly</h3><p>Booking status and current status are shown independently so changes are easy to understand.</p></div></div><div className="how-point"><div><h3>Only what’s available</h3><p>Journey, chart, coach and berth details appear only when returned by the configured data source.</p></div></div><div className="how-point"><div><h3>Independent by design</h3><p>RailCheck is an independent interface. Always confirm travel information with an official railway source.</p></div></div></div></section>
    </main>

    <footer className="footer">
      <div className="footer-main">
        <a href="#top" className="footer-brand">RailCheck<span>®</span></a>
        <nav className="footer-links" aria-label="Footer links">
          <a href="#terms" onClick={event => { event.preventDefault(); setLegalModal('terms') }}>Terms of Service</a>
          <a href="#privacy" onClick={event => { event.preventDefault(); setLegalModal('privacy') }}>Privacy Policy</a>
          <a href="https://www.indianrail.gov.in/enquiry/PNR/PnrEnquiry.jsp?locale=en" target="_blank" rel="noreferrer">Official PNR enquiry <ExternalLink size={13}/></a>
        </nav>
      </div>
      <div className="footer-meta">
        <span>© {new Date().getFullYear()} RailCheck. All rights reserved.</span>
        <span className="developer-credit">Made by Saptarshi Ghosh Dastidar</span>
      </div>
      <div className="footer-contact"><span>Independent service · Not affiliated with Indian Railways or IRCTC</span><a href="mailto:saptarshighosh2306@gmail.com">Contact RailCheck</a></div>
    </footer>

    {legalModal && <div className="modal-backdrop" role="presentation" onClick={event => { if (event.target === event.currentTarget) setLegalModal(null) }}>
      <section className="legal-modal" role="dialog" aria-modal="true" aria-labelledby="legal-modal-title" ref={legalDialogRef} tabIndex={-1}>
        <button className="modal-close" onClick={() => setLegalModal(null)} aria-label="Close dialog"><X size={19}/></button>
        <span className="eyebrow">RAILCHECK · {legalModal === 'terms' ? 'TERMS' : 'PRIVACY'}</span>
        <h2 id="legal-modal-title">{legalModal === 'terms' ? 'Terms of Service' : 'Privacy Policy'}</h2>
        <p className="legal-updated">Effective 28 October 2026</p>
        {legalModal === 'terms' ? <>
          <div className="legal-section"><h3>1. The service</h3><p>RailCheck is an independent PNR status interface operated by Saptarshi Ghosh Dastidar. It sends a PNR enquiry to API Mitra and displays the information returned. RailCheck does not issue, change, cancel, or manage railway tickets.</p></div>
          <div className="legal-section"><h3>2. Authorized use</h3><p>Submit only a PNR that you are authorized to check. Use RailCheck lawfully and do not interfere with the service, evade usage limits, or make requests in a way that disrupts the provider or other users.</p></div>
          <div className="legal-section"><h3>3. Status information</h3><p>Results come from API Mitra and may be delayed, incomplete, unavailable, or changed by the railway reservation system. RailCheck does not guarantee a booking outcome. Verify important journey details through an official Indian Railways or IRCTC channel before travel.</p></div>
          <div className="legal-section"><h3>4. Availability and provider terms</h3><p>Lookups depend on API Mitra access, its service limits, network availability, and its own terms. The API Mitra account holder is responsible for complying with the provider’s applicable limits and charges.</p></div>
          <div className="legal-section"><h3>5. Disclaimer</h3><p>To the extent permitted by applicable law, RailCheck is provided without a guarantee of uninterrupted availability or error-free results. Nothing in these terms limits rights or remedies that cannot legally be excluded.</p></div>
          <div className="legal-section"><h3>6. Contact</h3><p>Questions about these terms can be sent to <a href="mailto:saptarshighosh2306@gmail.com">saptarshighosh2306@gmail.com</a>.</p></div>
        </> : <>
          <div className="legal-section"><h3>1. Information handled</h3><p>When you request a lookup, RailCheck processes the 10-digit PNR you enter and the train, journey, and passenger status fields returned for that enquiry. A PNR can reveal details about a journey.</p></div>
          <div className="legal-section"><h3>2. How a lookup works</h3><p>Your browser sends the PNR to the RailCheck backend. The backend sends it to API Mitra over HTTPS to retrieve the status, then returns the response to your browser. API Mitra is an independent service and handles the enquiry under its own practices and terms.</p></div>
          <div className="legal-section"><h3>3. Storage and logs</h3><p>The current RailCheck application does not save PNRs or lookup results to a database or browser storage. It processes them in memory to complete the request. Hosting and server infrastructure may keep routine technical logs. API Mitra may keep request records; RailCheck does not control the provider’s retention period or logs.</p></div>
          <div className="legal-section"><h3>4. Other services and device features</h3><p>The page loads DM Sans and Manrope font files from Google Fonts, so your browser connects to Google to retrieve those files. The PNR is not sent to Google by RailCheck. If you choose “Copy PNR,” the PNR is written to your device clipboard. Your light or dark mode choice is saved in this browser so it is remembered on your next visit. RailCheck does not currently use advertising trackers, analytics, or account cookies.</p></div>
          <div className="legal-section"><h3>5. Your choices and requests</h3><p>You can choose not to submit a PNR. For privacy questions or requests concerning information handled by RailCheck, contact us by email. Because RailCheck does not keep lookup records, it may not be able to locate a past enquiry. Requests about API Mitra’s handling or retention should be directed to API Mitra.</p></div>
          <div className="legal-section"><h3>6. Contact</h3><p>For privacy questions, email <a href="mailto:saptarshighosh2306@gmail.com">saptarshighosh2306@gmail.com</a>.</p></div>
        </>}
        <button className="modal-primary" onClick={() => setLegalModal(null)}>Close</button>
      </section>
    </div>}

  </div>
}
