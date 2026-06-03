import { useState, useEffect } from 'react';

/**
 * DevModeToggle — a toggle button visually matching DarkModeToggle.
 * Persists state in localStorage('devMode'). Can optionally dispatch to
 * the DPDP store when a dispatch function is provided.
 */
export default function DevModeToggle({ dispatch }) {
  const [isDevMode, setIsDevMode] = useState(() => {
    return localStorage.getItem('devMode') === 'true';
  });

  useEffect(() => {
    localStorage.setItem('devMode', String(isDevMode));
    // If a store dispatch is wired up, keep store in sync
    if (dispatch) {
      dispatch({ type: 'SET_DEV_MODE', payload: isDevMode });
    }
  }, [isDevMode, dispatch]);

  return (
    <button
      id="devModeToggle"
      onClick={() => setIsDevMode(v => !v)}
      className="dev-mode-toggle relative flex items-center justify-center w-10 h-10 rounded-full transition-all duration-300 hover:bg-white/10 active:scale-95 focus:outline-none focus:ring-2 focus:ring-white/40 text-white cursor-pointer group"
      aria-label={isDevMode ? 'Disable Developer Mode' : 'Enable Developer Mode'}
      title={isDevMode ? 'Disable Developer Mode' : 'Enable Developer Mode'}
    >
      <div className="relative w-6 h-6 flex items-center justify-center overflow-hidden">
        {/* Code bracket icon — active state */}
        <svg
          className={`absolute w-5 h-5 transition-all duration-500 transform ${
            isDevMode ? 'scale-100 rotate-0 opacity-100' : 'scale-0 -rotate-90 opacity-0'
          } text-emerald-400 group-hover:rotate-12`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          viewBox="0 0 24 24"
        >
          <polyline points="16 18 22 12 16 6" />
          <polyline points="8 6 2 12 8 18" />
        </svg>

        {/* Terminal icon — inactive state */}
        <svg
          className={`absolute w-5 h-5 transition-all duration-500 transform ${
            isDevMode ? 'scale-0 rotate-90 opacity-0' : 'scale-100 rotate-0 opacity-100'
          } text-white/70 group-hover:-rotate-12`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          viewBox="0 0 24 24"
        >
          <polyline points="4 17 10 11 4 5" />
          <line x1="12" y1="19" x2="20" y2="19" />
        </svg>
      </div>

      {/* "DEV" label pill */}
      <span className={`dev-mode-label ${isDevMode ? 'active' : ''}`}>
        Dev
      </span>
    </button>
  );
}
