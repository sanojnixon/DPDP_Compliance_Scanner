import React from 'react';
import { useNavigate } from 'react-router-dom';
import DarkModeToggle from '../DarkModeToggle';
import DevModeToggle from '../DevModeToggle';
import { useDpdpStore } from './useDpdpStore';

export default function PageShell({ children, currentStep = 1, totalSteps = 2, centered = true }) {
  const navigate = useNavigate();
  const { dispatch } = useDpdpStore();

  return (
    <div className="dpdp-page-shell">
      {/* SIBerNet-style Header */}
      <header className="dpdp-header">
        <div className="dpdp-header-inner">
          <img
            src="/SIB_Logo.png"
            alt="South Indian Bank"
            className="dpdp-logo"
            onClick={() => navigate('/')}
            onError={e => { e.currentTarget.style.display = 'none'; }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div className="dpdp-header-badge">
              <span className="dpdp-header-badge-dot" />
              DPDP Compliance Scanner
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <DarkModeToggle />
              <div style={{ width: '1px', height: '20px', background: 'rgba(255,255,255,0.18)', borderRadius: '1px' }} />
              <DevModeToggle dispatch={dispatch} />
            </div>
          </div>
        </div>
      </header>

      {/* Step Progress Bar */}
      <div className="dpdp-step-bar">
        <div className="dpdp-step-bar-inner">
          {Array.from({ length: totalSteps }, (_, i) => {
            const step = i + 1;
            const done = step < currentStep;
            const active = step === currentStep;
            return (
              <React.Fragment key={step}>
                <div className={`dpdp-step-node ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
                  <div className="dpdp-step-circle">
                    {done ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                    ) : (
                      <span>{step}</span>
                    )}
                  </div>
                  <span className="dpdp-step-label">
                    {step === 1 ? 'Process Identification' : 'PII Selection'}
                  </span>
                </div>
                {i < totalSteps - 1 && <div className={`dpdp-step-line ${done ? 'done' : ''}`} />}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Page Content */}
      <main className={`dpdp-main${centered ? ' dpdp-main--centered' : ''}`}>
        {children}
      </main>

      {/* Footer */}
      <footer className="dpdp-footer">
        <div className="dpdp-footer-inner">
          <p className="dpdp-footer-text">© 2026 South Indian Bank. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
