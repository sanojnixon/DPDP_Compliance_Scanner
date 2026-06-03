import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './login.css'
import DarkModeToggle from './DarkModeToggle'
import DevModeToggle from './DevModeToggle'

/* ── Eye icon SVG paths ──────────────────────────────────────── */
const EYE_OPEN = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'
const EYE_OFF = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'

export default function LoginPage() {
  const navigate = useNavigate()
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [alertMsg, setAlertMsg] = useState('')
  const [alertOn, setAlertOn] = useState(false)

  const userIdRef = useRef(null)
  const passwordRef = useRef(null)
  const btnRef = useRef(null)

  /* Keep btn-primary loading class in sync */
  useEffect(() => {
    const btn = btnRef.current
    if (!btn) return
    if (loading) {
      btn.classList.add('loading')
      btn.disabled = true
    } else {
      btn.classList.remove('loading')
      btn.disabled = false
    }
  }, [loading])

  function togglePassword() {
    setShowPw(v => !v)
    const btn = document.getElementById('togglePw')
    if (btn) {
      btn.setAttribute('aria-label', !showPw ? 'Hide password' : 'Show password')
    }
  }

  function handleForgot(e) {
    e.preventDefault()
    alert('Please contact your system administrator or the SIB Digital Helpdesk to reset your password.')
  }

  async function handleLogin(e) {
    e.preventDefault()
    const userId = userIdRef.current.value.trim()
    const password = passwordRef.current.value

    setAlertOn(false)

    if (!userId || !password) {
      setAlertMsg('Please enter both your User ID and password.')
      setAlertOn(true)
      return
    }

    setLoading(true)

    try {
      const response = await fetch('http://localhost:5000/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, password })
      })
      
      const data = await response.json()
      
      setLoading(false)
      if (response.ok && data.token) {
        // Success! Store token and route to upload page
        localStorage.setItem('token', data.token)
        navigate('/upload')
      } else {
        // Failure
        setAlertMsg(data.error || 'Invalid User ID or password. Please try again.')
        setAlertOn(true)
      }
      
    } catch (err) {
      console.error(err);
      setLoading(false)
      setAlertMsg('Failed to connect to the authentication server.')
      setAlertOn(true)
    }
  }

  return (
    <>

      {/* =========================================================
          TOP HEADER — exact SIB portal bar
          ========================================================= */}
      <header className="w-full bg-sib-maroon flex-shrink-0 z-10">
        <div className="max-w-[1200px] mx-auto flex items-center justify-between px-5" style={{ height: '90px' }}>
          {/* Main Website Logo */}
          <img
            src="/SIB_Logo.png"
            alt="South Indian Bank"
            className="w-auto object-contain"
            style={{ height: '71.5px' }}
            onError={e => { e.currentTarget.style.display = 'none' }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <DarkModeToggle />
            <div style={{ width: '1px', height: '20px', background: 'rgba(255,255,255,0.18)', borderRadius: '1px' }} />
            <DevModeToggle />
          </div>
        </div>
      </header>

      {/* =========================================================
          MAIN — centered login card
          ========================================================= */}
      <main className="flex-1 flex items-center justify-center px-4 py-10">

        {/* Card: split layout */}
        <div className="card-enter flex w-full max-w-[900px] min-h-[560px] rounded-2xl overflow-hidden shadow-card">

          {/* =======================================================
              LEFT PANEL — Maroon brand side
              ======================================================= */}
          <div
            className="stripe-bg relative hidden md:flex flex-col justify-between w-[390px] flex-shrink-0 p-10 overflow-hidden"
            style={{ background: 'linear-gradient(155deg, #8A1519 0%, #B5131A 45%, #C02025 100%)' }}>
            <div className="geo-1"></div>
            <div className="geo-2"></div>

            <div className="relative z-10 flex flex-col gap-10 stagger-l">

              {/* Logo block */}
              <div>
                <img src="https://sibernet.southindianbank.bank.in/corp/static/img/siblogowhite_latest.png"
                  alt="South Indian Bank" className="h-[38px] w-auto object-contain mb-8"
                  onError={e => { e.currentTarget.style.display = 'none' }} />
                {/* Headline */}
                <h2 className="font-display text-white text-[36px] leading-[1.15] font-normal tracking-tight mb-4">
                  DPDP Compliance Scanner<br />&amp; Accessibility Auditor
                </h2>
                <p className="text-white/55 text-[13px] leading-relaxed font-light max-w-[270px]">
                  AI-powered DPDP compliance scanning and accessibility auditing — built for India's banking ecosystem.
                </p>
              </div>

              {/* Feature badges */}
              <div className="flex flex-col gap-3">
                <div className="feature-badge flex items-center gap-3 rounded-full px-4 py-2.5 w-fit">
                  <span className="text-[15px] leading-none">🛡️</span>
                  <span className="text-white/85 text-[12.5px] font-medium tracking-wide">DPDP Act Compliance</span>
                </div>
                <div className="feature-badge flex items-center gap-3 rounded-full px-4 py-2.5 w-fit">
                  <span className="text-[15px] leading-none">♿</span>
                  <span className="text-white/85 text-[12.5px] font-medium tracking-wide">AI Accessibility Auditor</span>
                </div>
                <div className="feature-badge flex items-center gap-3 rounded-full px-4 py-2.5 w-fit">
                  <span className="text-[15px] leading-none">📊</span>
                  <span className="text-white/85 text-[12.5px] font-medium tracking-wide">Real-time Reports</span>
                </div>
              </div>

            </div>

            {/* Footer note */}
            <p className="relative z-10 text-white/30 text-[10.5px] tracking-[0.1em] uppercase font-medium">
              Digital and Technology Department
            </p>
          </div>

          {/* =======================================================
              RIGHT PANEL — White form side
              ======================================================= */}
          <div className="flex-1 flex flex-col justify-center px-10 py-12 bg-white">
            <div className="w-full max-w-[360px] mx-auto stagger-r">

              {/* Eyebrow */}
              <div className="flex items-center gap-2 mb-5">
                <span className="w-1.5 h-1.5 rounded-full bg-sib-maroon animate-pulse-dot"></span>
                <span className="text-sib-maroon text-[10.5px] font-bold tracking-[0.12em] uppercase">Secure Access</span>
              </div>

              {/* Titles */}
              <div className="mb-8">
                <h1 className="text-[24px] font-bold text-gray-900 leading-tight tracking-tight mb-1.5">
                  Sign in to your account
                </h1>
              </div>

              {/* Form */}
              <form id="loginForm" noValidate onSubmit={handleLogin} className="flex flex-col gap-4">

                {/* Alert */}
                <div id="alertBox"
                  className={`alert-box items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-[12.5px] font-medium rounded-lg px-3.5 py-2.5${alertOn ? ' show' : ''}`}
                  role="alert" aria-live="polite">
                  <span className="text-red-400 flex-shrink-0">⚠</span>
                  <span id="alertMsg">{alertMsg}</span>
                </div>

                {/* User ID */}
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="userId" className="text-[11.5px] font-semibold text-gray-500 tracking-wide uppercase">User ID /
                    Employee ID</label>
                  <div className="relative field-wrap">
                    <span
                      className="icon-left absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-300 pointer-events-none transition-colors duration-200">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                        strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="8" r="4" />
                        <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
                      </svg>
                    </span>
                    <input ref={userIdRef} id="userId" type="text" name="userId" placeholder="Enter your User ID"
                      autoComplete="username" autoCapitalize="none" spellCheck={false} required aria-required="true"
                      className="field-input w-full h-[46px] rounded-lg pl-10 pr-4 text-[14px] text-gray-800 font-normal" />
                  </div>
                </div>

                {/* Password */}
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="password"
                    className="text-[11.5px] font-semibold text-gray-500 tracking-wide uppercase">Password</label>
                  <div className="relative field-wrap">
                    <span
                      className="icon-left absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-300 pointer-events-none transition-colors duration-200">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                        strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                    </span>
                    <input ref={passwordRef} id="password" type={showPw ? 'text' : 'password'} name="password"
                      placeholder="Enter your password" autoComplete="current-password" required aria-required="true"
                      className="field-input w-full h-[46px] rounded-lg pl-10 pr-11 text-[14px] text-gray-800 font-normal" />
                    <button type="button" id="togglePw" aria-label="Show password" onClick={togglePassword}
                      className="toggle-pw absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-300 cursor-pointer">
                      <svg id="eyeIcon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                        dangerouslySetInnerHTML={{ __html: showPw ? EYE_OFF : EYE_OPEN }}
                      />
                    </button>
                  </div>
                </div>

                {/* Forgot password */}
                <div className="flex justify-end -mt-1">
                  <a href="#" id="forgotLink" onClick={handleForgot}
                    className="text-sib-soft text-[12px] font-medium hover:text-sib-maroon transition-colors duration-200">
                    Forgot password?
                  </a>
                </div>

                {/* Submit */}
                <button ref={btnRef} type="submit" id="loginBtn"
                  className="btn-primary relative w-full h-[50px] rounded-lg text-white text-[14px] font-bold tracking-[0.06em] uppercase mt-1 cursor-pointer">
                  <span className="btn-label">Sign In</span>
                  <span className="btn-spinner" aria-hidden="true"><span className="spin-ring"></span></span>
                </button>

              </form>

              {/* Divider */}
              <div className="flex items-center gap-3 mt-7 mb-4">
                <div className="flex-1 h-px bg-gray-100"></div>
                <span className="text-gray-300 text-[10px] font-semibold tracking-widest uppercase">Protected Connection</span>
                <div className="flex-1 h-px bg-gray-100"></div>
              </div>

              {/* Security badges */}
              <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5">
                <div className="flex items-center gap-1.5 text-gray-400 text-[11px] font-medium">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                  256-bit TLS
                </div>
                <div className="flex items-center gap-1.5 text-gray-400 text-[11px] font-medium">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 12l2 2 4-4" />
                    <circle cx="12" cy="12" r="10" />
                  </svg>
                  DPDP Compliant
                </div>
                <div className="flex items-center gap-1.5 text-gray-400 text-[11px] font-medium">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="7" width="20" height="14" rx="2" />
                    <path d="M16 7V4a4 4 0 0 0-8 0v3" />
                  </svg>
                  MeitY Certified
                </div>
              </div>

            </div>
          </div>
          {/* /right panel */}

        </div>
        {/* /card */}

      </main >

      {/* =========================================================
          FOOTER
          ========================================================= */}
      < footer className="w-full bg-[#2F2F2F] py-3 flex-shrink-0" >
        <div className="max-w-[1200px] mx-auto px-5 flex flex-col sm:flex-row items-center justify-between gap-1.5">
          <p className="text-white/35 text-[11px] font-medium">&copy; 2026 South Indian Bank. All rights reserved.</p>
          <p className="text-white/25 text-[10.5px]">Secured by SIB Digital Infrastructure &middot; DPDP Act 2023</p>
        </div>
      </footer >

    </>
  )
}