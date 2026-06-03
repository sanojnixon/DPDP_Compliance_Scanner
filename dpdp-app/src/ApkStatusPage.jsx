import { useState, useEffect } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { useDpdpStore } from './dpdp/useDpdpStore.jsx';
import DarkModeToggle from './DarkModeToggle';

export default function ApkStatusPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { dispatch } = useDpdpStore();

  const [jobData, setJobData] = useState({
    status: 'queued',
    progress: 0,
    message: 'Waiting to start...',
    screenshot_count: 0,
    image_ids: [],
    static_info: location.state?.staticInfo || {},
    error: null,
  });
  const [startError, setStartError] = useState(null);

  const token = localStorage.getItem('token');

  // Kick off the emulator navigation as soon as the page mounts
  useEffect(() => {
    if (!jobId || !token) return;
    fetch(`http://localhost:5000/api/apk/start/${jobId}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); })
      .catch(e => setStartError(`Could not start job: ${e.message}`));
  }, [jobId, token]);  

  // Poll every 2 seconds
  useEffect(() => {
    if (!jobId || !token) return;
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:5000/api/apk/status/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        setJobData(data);

        if (data.status === 'done') {
          clearInterval(poll);
          dispatch({ type: 'SET_IMAGE_IDS', payload: data.image_ids });
          navigate('/dpdp/process');
        } else if (data.status === 'failed') {
          clearInterval(poll);
        }
      } catch (e) {
        console.error('[APK Poll] error:', e);
      }
    }, 2000);
    return () => clearInterval(poll);
  }, [jobId, token]); // eslint-disable-line

  const si = jobData.static_info || {};
  const isDone = jobData.status === 'done';
  const isFailed = jobData.status === 'failed';
  const isActive = !isDone && !isFailed;

  const STATUS_LABELS = {
    queued: 'Queued',
    ready: 'Ready',
    navigating: 'Navigating App',
    processing: 'Saving Screenshots',
    done: 'Complete',
    failed: 'Failed',
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F8F9FA] font-sans">
      {/* Header */}
      <header className="w-full bg-sib-maroon flex-shrink-0 z-10 shadow-sm">
        <div className="max-w-[1200px] mx-auto flex items-center justify-between px-5" style={{ height: '90px' }}>
          <img
            src="/SIB_Logo.png"
            alt="South Indian Bank"
            className="w-auto object-contain cursor-pointer"
            style={{ height: '71.5px' }}
            onClick={() => navigate('/')}
            onError={e => { e.currentTarget.style.display = 'none'; }}
          />
          <DarkModeToggle />
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-12">
        <div style={{
          width: '100%', maxWidth: 560,
          background: '#fff', borderRadius: 16,
          boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
          padding: '40px 36px',
        }}>
          {/* Header */}
          <div style={{ marginBottom: 28 }}>
            <span style={{
              fontSize: 12, fontWeight: 700, letterSpacing: '0.08em',
              color: '#8B1A1A', textTransform: 'uppercase',
            }}>APK Analysis</span>
            <h1 style={{ margin: '6px 0 4px', fontSize: 22, fontWeight: 700, color: '#111' }}>
              {si.app_name || si.package_name || 'Analysing APK…'}
            </h1>
            {si.package_name && (
              <p style={{ margin: 0, fontSize: 12, color: '#6B7280', fontFamily: 'monospace' }}>
                {si.package_name}
              </p>
            )}
          </div>

          {/* Start error */}
          {startError && (
            <div style={{
              background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8,
              padding: '10px 14px', marginBottom: 20, fontSize: 13, color: '#991B1B',
            }}>
              ⚠ {startError}
            </div>
          )}

          {/* Status badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
            {isActive && (
              <span style={{
                display: 'inline-block', width: 10, height: 10,
                borderRadius: '50%', background: '#2563EB',
                animation: 'pulse 1.4s ease-in-out infinite',
              }} />
            )}
            <span style={{
              fontSize: 13, fontWeight: 700,
              color: isFailed ? '#DC2626' : isDone ? '#16A34A' : '#2563EB',
            }}>
              {STATUS_LABELS[jobData.status] || jobData.status}
            </span>
            {jobData.message && (
              <span style={{ fontSize: 12, color: '#6B7280' }}>— {jobData.message}</span>
            )}
          </div>

          {/* Progress bar */}
          <div style={{
            height: 8, background: '#F3F4F6', borderRadius: 99,
            overflow: 'hidden', marginBottom: 24,
          }}>
            <div style={{
              height: '100%', borderRadius: 99,
              background: isFailed ? '#DC2626' : isDone ? '#16A34A' : '#2563EB',
              width: `${jobData.progress}%`,
              transition: 'width 0.5s ease',
            }} />
          </div>

          {/* Screenshot counter */}
          <div style={{
            display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap',
          }}>
            {[
              { label: 'Screenshots captured', value: jobData.screenshot_count },
              { label: 'Progress', value: `${jobData.progress}%` },
            ].map(({ label, value }) => (
              <div key={label} style={{
                flex: 1, minWidth: 120, background: '#F9FAFB',
                border: '1px solid #E5E7EB', borderRadius: 10,
                padding: '14px 16px',
              }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: '#111', marginBottom: 2 }}>{value}</div>
                <div style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
              </div>
            ))}
          </div>

          {/* Static info chips */}
          {si.permissions?.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                Permissions ({si.permissions.length})
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {si.permissions.slice(0, 12).map(p => (
                  <span key={p} style={{
                    background: '#FEF2F2', color: '#991B1B',
                    padding: '2px 8px', borderRadius: 4,
                    fontSize: 11, fontFamily: 'monospace',
                  }}>
                    {p.replace('android.permission.', '')}
                  </span>
                ))}
                {si.permissions.length > 12 && (
                  <span style={{ fontSize: 11, color: '#9CA3AF', padding: '2px 4px' }}>
                    +{si.permissions.length - 12} more
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Error panel */}
          {isFailed && jobData.error && (
            <div style={{
              background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 10,
              padding: '14px 16px', marginBottom: 20,
            }}>
              <p style={{ margin: '0 0 4px', fontSize: 13, fontWeight: 700, color: '#991B1B' }}>Analysis failed</p>
              <p style={{ margin: 0, fontSize: 12, color: '#7F1D1D', fontFamily: 'monospace' }}>{jobData.error}</p>
              <button
                onClick={() => navigate('/upload')}
                style={{
                  marginTop: 12, padding: '6px 16px', borderRadius: 6,
                  background: '#8B1A1A', color: '#fff', border: 'none',
                  fontSize: 12, fontWeight: 600, cursor: 'pointer',
                }}
              >
                Try again
              </button>
            </div>
          )}

          {/* Done state */}
          {isDone && (
            <div style={{
              background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: 10,
              padding: '14px 16px', fontSize: 13, color: '#166534',
            }}>
              ✓ {jobData.screenshot_count} screens captured — redirecting to compliance scan…
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full bg-[#2F2F2F] py-3 flex-shrink-0">
        <div className="max-w-[1200px] mx-auto px-5 flex items-center justify-between">
          <p className="text-white/35 text-[11px] font-medium">&copy; 2026 South Indian Bank. All rights reserved.</p>
        </div>
      </footer>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
