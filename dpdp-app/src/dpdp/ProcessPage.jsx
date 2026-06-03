import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import PageShell from './PageShell';
import { useDpdpStore } from './useDpdpStore.jsx';
import './dpdp.css';

export default function ProcessPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, dispatch } = useDpdpStore();

  // Persist imageIds passed via router state into the DPDP store
  useEffect(() => {
    const ids = location.state?.imageIds;
    // Always reset stale state first — images are deleted from DB after scanning,
    // so carrying forward old imageIds will cause 404 on the next scan.
    dispatch({ type: 'RESET' });
    if (ids && ids.length > 0) {
      dispatch({ type: 'SET_IMAGE_IDS', payload: ids });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelect = (value) => {
    dispatch({ type: 'SET_IS_PROCESS', payload: value });
  };

  const handleContinue = () => {
    if (state.isProcess === null) return;
    navigate('/dpdp/pii');
  };

  const canContinue = state.isProcess !== null && (state.isProcess === false || state.processType.trim().length > 0);

  return (
    <PageShell currentStep={1} totalSteps={2}>
      <div className="process-card">
        <div className="process-tag">Step 1 of 2</div>
        <h1 className="process-title">Is this a Process?</h1>
        <p className="process-subtitle">
          Help us understand the nature of your document to tailor the DPDP compliance scan accordingly.
        </p>

        <div className="process-options">
          {/* Yes */}
          <button
            id="process-yes-btn"
            className={`process-option-btn ${state.isProcess === true ? 'selected' : ''}`}
            onClick={() => handleSelect(true)}
          >
            <div className="process-option-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </div>
            <span className="process-option-label">Yes</span>
          </button>

          {/* No */}
          <button
            id="process-no-btn"
            className={`process-option-btn ${state.isProcess === false ? 'selected' : ''}`}
            onClick={() => handleSelect(false)}
          >
            <div className="process-option-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </div>
            <span className="process-option-label">No</span>
          </button>
        </div>

        {state.isProcess === true && (
          <div className="process-input-group">
            <label htmlFor="process-type-input" className="process-input-label">
              What type of Process is it?
            </label>
            <input
              id="process-type-input"
              type="text"
              className="process-input"
              placeholder="e.g. Loan Application, KYC Verification, Account Opening…"
              value={state.processType}
              onChange={e => dispatch({ type: 'SET_PROCESS_TYPE', payload: e.target.value })}
              autoFocus
            />
          </div>
        )}

        <button
          id="process-continue-btn"
          className="btn-primary"
          disabled={!canContinue}
          onClick={handleContinue}
          style={{
            width: '100%',
            height: '50px',
            borderRadius: '10px',
            color: '#fff',
            fontSize: '14px',
            fontWeight: 700,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            border: 'none',
            cursor: canContinue ? 'pointer' : 'not-allowed',
            opacity: canContinue ? 1 : 0.5,
            fontFamily: '\'Plus Jakarta Sans\', Arial, sans-serif',
          }}
        >
          Continue to PII Selection →
        </button>
      </div>
    </PageShell>
  );
}
