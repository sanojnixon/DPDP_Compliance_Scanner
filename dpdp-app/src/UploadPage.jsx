import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import DarkModeToggle from './DarkModeToggle';
import DevModeToggle from './DevModeToggle';
import { useDpdpStore } from './dpdp/useDpdpStore.jsx';
import './dpdp/dpdp.css';

export default function UploadPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { state: dpdpState, dispatch } = useDpdpStore();
  const devMode = dpdpState.devMode;

  // ── Baseline comparison state (dev mode only) ──────────────────
  const [baselines, setBaselines] = useState([]);
  const [baselinesLoading, setBaselinesLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // baseline object or null

  const fetchBaselines = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    setBaselinesLoading(true);
    try {
      const res = await fetch('http://localhost:5000/api/dev/baseline', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setBaselines(await res.json());
    } catch (err) {
      console.error('Failed to fetch baselines:', err);
    } finally {
      setBaselinesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (devMode) fetchBaselines();
  }, [devMode, fetchBaselines]);

  const handleDeleteBaseline = async (bl) => {
    const token = localStorage.getItem('token');
    try {
      const res = await fetch(`http://localhost:5000/api/dev/baseline/${bl.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        // If the deleted baseline was selected, clear selection
        if (dpdpState.selectedBaseline?.id === bl.id) {
          dispatch({ type: 'SELECTED_BASELINE', payload: null });
        }
        fetchBaselines();
      }
    } catch (err) {
      console.error('Delete baseline failed:', err);
    } finally {
      setDeleteConfirm(null);
    }
  };

  const handleSelectBaseline = (bl) => {
    if (dpdpState.selectedBaseline?.id === bl.id) {
      dispatch({ type: 'SELECTED_BASELINE', payload: null });
    } else {
      dispatch({ type: 'SELECTED_BASELINE', payload: { id: bl.id, file_name: bl.file_name } });
    }
  };

  // ── Screenshot mode state ──────────────────────────────────────
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const inputRef = useRef(null);

  // ── APK mode state ─────────────────────────────────────────────
  const [mode, setMode] = useState('screenshots'); // 'screenshots' | 'apk'
  const [apkFile, setApkFile] = useState(null);
  const [isUploadingApk, setIsUploadingApk] = useState(false);
  const apkInputRef = useRef(null);

  // ── Screenshot handlers ────────────────────────────────────────
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndAddFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files.length > 0) {
      validateAndAddFiles(Array.from(e.target.files));
    }
  };

  const validateAndAddFiles = (selectedFiles) => {
    const validFiles = selectedFiles.filter(f => f.type === 'image/jpeg' || f.type === 'image/png');
    if (validFiles.length !== selectedFiles.length) {
      alert('Some files were ignored. Please only upload .png or .jpg image files.');
    }
    if (validFiles.length > 0) setFiles(prev => [...prev, ...validFiles]);
  };

  const removeFile = (indexToRemove) => setFiles(files.filter((_, i) => i !== indexToRemove));

  const triggerInput = () => inputRef.current.click();

  const handleContinue = async () => {
    if (files.length === 0) return;
    setIsUploading(true);
    const token = localStorage.getItem('token');
    if (!token) { alert('Authentication error. Please log in again.'); navigate('/'); return; }
    const formData = new FormData();
    files.forEach(file => formData.append('images', file));
    try {
      const response = await fetch('http://localhost:5000/api/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (response.ok) {
        const data = await response.json();
        setIsUploading(false);
        navigate('/select', { state: { imageIds: data.image_ids } });
      } else {
        const errorData = await response.json();
        alert('Upload failed: ' + (errorData.error || 'Unknown error'));
        setIsUploading(false);
      }
    } catch (err) {
      console.error(err);
      alert('Network error connecting to the server.');
      setIsUploading(false);
    }
  };

  // ── APK handlers ───────────────────────────────────────────────
  const handleApkChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      if (f.name.endsWith('.apk')) setApkFile(f);
      else alert('Please upload a valid .apk file.');
    }
  };

  const handleApkContinue = async () => {
    if (!apkFile) return;
    setIsUploadingApk(true);
    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('apk', apkFile);
    try {
      const res = await fetch('http://localhost:5000/api/apk/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setIsUploadingApk(false);
      navigate(`/apk/status/${data.job_id}`, { state: { staticInfo: data.static_info } });
    } catch (err) {
      console.error(err);
      alert('Network error connecting to the server.');
      setIsUploadingApk(false);
    }
  };

  return (
    <>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <DarkModeToggle />
            <div style={{ width: '1px', height: '20px', background: 'rgba(255,255,255,0.18)', borderRadius: '1px' }} />
            <DevModeToggle dispatch={dispatch} />
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-12">
        <div className="w-full max-w-[700px] bg-white rounded-2xl shadow-card p-10 flex flex-col items-center">

          {/* Tab switcher — outside any form element */}
          <div className="flex w-full mb-8 rounded-xl overflow-hidden border border-gray-200">
            <button
              type="button"
              onClick={() => setMode('screenshots')}
              className={`flex-1 py-3 text-[13px] font-semibold transition-colors ${mode === 'screenshots' ? 'bg-sib-maroon text-white' : 'bg-gray-50 text-gray-500 hover:bg-gray-100'}`}
            >
              📷 Screenshots
            </button>
            <button
              type="button"
              onClick={() => setMode('apk')}
              className={`flex-1 py-3 text-[13px] font-semibold transition-colors ${mode === 'apk' ? 'bg-sib-maroon text-white' : 'bg-gray-50 text-gray-500 hover:bg-gray-100'}`}
            >
              📦 APK File
            </button>
          </div>

          {/* ── Screenshots mode ── */}
          {mode === 'screenshots' && (
            <>
              <div className="mb-8 text-center">
                <h1 className="text-[28px] font-display text-gray-900 font-semibold mb-2">Upload Screenshots</h1>
                <p className="text-[14px] text-gray-500 font-normal">
                  Upload screenshot images (.jpg or .png) to scan for DPDP compliance.
                </p>
              </div>

              <form
                className={`w-full border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center transition-colors duration-200 cursor-pointer
                  ${dragActive ? 'border-sib-maroon bg-red-50' : 'border-gray-300 bg-gray-50 hover:bg-gray-100'}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={triggerInput}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept=".png, .jpg, .jpeg"
                  multiple
                  onChange={handleChange}
                  className="hidden"
                />
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-gray-400 mb-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 15v4c0 1.1.9 2 2 2h14a2 2 0 0 0 2-2v-4M17 8l-5-5-5 5M12 3v12" />
                </svg>
                <p className="text-gray-700 text-[15px] font-medium mb-1">Drag and drop your images here</p>
                <p className="text-gray-400 text-[13px]">or click to browse from your computer (select multiple)</p>

                {files.length > 0 && (
                  <div className="mt-6 w-full max-w-[500px] flex flex-col gap-3 max-h-[200px] overflow-y-auto pr-2">
                    {files.map((f, i) => (
                      <div key={i} className="p-3 bg-white rounded-lg shadow-sm border border-gray-200 flex items-center justify-between w-full">
                        <div className="flex items-center gap-3 overflow-hidden">
                          <div className="w-10 h-10 flex-shrink-0 rounded bg-red-50 flex items-center justify-center text-sib-maroon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                              <circle cx="8.5" cy="8.5" r="1.5" />
                              <polyline points="21 15 16 10 5 21" />
                            </svg>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate" title={f.name}>{f.name}</p>
                            <p className="text-xs text-gray-500">{(f.size / 1024 / 1024).toFixed(2)} MB</p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                          className="ml-2 text-gray-400 hover:text-red-500 transition-colors p-2 rounded-full hover:bg-gray-100"
                        >
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </form>

              {/* Continue button OUTSIDE the form */}
              <button
                onClick={handleContinue}
                disabled={files.length === 0 || isUploading}
                className={`btn-primary w-full max-w-[300px] h-[50px] rounded-lg text-white text-[14px] font-bold tracking-[0.06em] uppercase mt-10 transition-all duration-300
                  ${files.length === 0 || isUploading ? 'opacity-50 cursor-not-allowed grayscale' : 'cursor-pointer hover:shadow-lg'}`}
              >
                {isUploading ? 'Uploading...' : `Upload ${files.length} Image${files.length !== 1 ? 's' : ''} & Continue`}
              </button>
            </>
          )}

          {/* ── APK mode ── */}
          {mode === 'apk' && (
            <>
              <div className="mb-8 text-center">
                <h1 className="text-[28px] font-display text-gray-900 font-semibold mb-2">Upload APK File</h1>
                <p className="text-[14px] text-gray-500 font-normal">
                  Upload an Android APK — the app will be launched in an emulator and key screens captured automatically.
                </p>
              </div>

              <div
                onClick={() => apkInputRef.current.click()}
                className="w-full border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center cursor-pointer transition-colors border-gray-300 bg-gray-50 hover:bg-gray-100"
              >
                <input
                  ref={apkInputRef}
                  type="file"
                  accept=".apk"
                  onChange={handleApkChange}
                  className="hidden"
                />
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-gray-400 mb-4">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path strokeLinecap="round" d="M8 12h8M12 8v8" />
                </svg>
                <p className="text-gray-700 text-[15px] font-medium mb-1">Click to select an APK file</p>
                <p className="text-gray-400 text-[13px]">Android Package (.apk) only</p>

                {apkFile && (
                  <div className="mt-6 p-3 bg-white rounded-lg shadow-sm border border-gray-200 flex items-center gap-3 w-full max-w-[400px]">
                    <div className="w-10 h-10 flex-shrink-0 rounded bg-red-50 flex items-center justify-center text-sib-maroon text-[11px] font-bold">APK</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{apkFile.name}</p>
                      <p className="text-xs text-gray-500">{(apkFile.size / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Continue button OUTSIDE the drop zone div, not inside any form */}
              <button
                onClick={handleApkContinue}
                disabled={!apkFile || isUploadingApk}
                className={`btn-primary w-full max-w-[300px] h-[50px] rounded-lg text-white text-[14px] font-bold tracking-[0.06em] uppercase mt-10 transition-all duration-300
                  ${!apkFile || isUploadingApk ? 'opacity-50 cursor-not-allowed grayscale' : 'cursor-pointer hover:shadow-lg'}`}
              >
                {isUploadingApk ? 'Uploading...' : 'Analyse APK'}
              </button>
            </>
          )}

        </div>

        {/* ── Baseline Comparison Section (dev mode only) ── */}
        {devMode && (
          <div className="baseline-compare-section">
            <div className="baseline-compare-header">
              <div className="baseline-compare-badge">🛠 DEV</div>
              <div>
                <h3 className="baseline-compare-title">Compare against baseline</h3>
                <p className="baseline-compare-subtitle">
                  Select a saved baseline to compare correction status after the next scan.
                </p>
              </div>
            </div>

            {baselinesLoading ? (
              <div className="baseline-compare-empty">Loading baselines…</div>
            ) : baselines.length === 0 ? (
              <div className="baseline-compare-empty">
                No baseline files saved yet. Run a scan and save one from the Dev Tools tab.
              </div>
            ) : (
              <div className="baseline-list">
                {baselines.map(bl => (
                  <div
                    key={bl.id}
                    className={`baseline-list-item ${dpdpState.selectedBaseline?.id === bl.id ? 'selected' : ''}`}
                    onClick={() => handleSelectBaseline(bl)}
                  >
                    <div className="baseline-list-item-radio">
                      {dpdpState.selectedBaseline?.id === bl.id && (
                        <div className="baseline-list-item-radio-dot" />
                      )}
                    </div>
                    <div className="baseline-list-item-info">
                      <span className="baseline-list-item-name">{bl.file_name}</span>
                      <span className="baseline-list-item-date">
                        {new Date(bl.created_at).toLocaleString()}
                      </span>
                    </div>
                    <button
                      className="baseline-list-item-delete"
                      title="Delete baseline"
                      onClick={e => { e.stopPropagation(); setDeleteConfirm(bl); }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        <line x1="10" y1="11" x2="10" y2="17" />
                        <line x1="14" y1="11" x2="14" y2="17" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}

            {dpdpState.selectedBaseline && (
              <div className="baseline-compare-selected">
                ✓ Comparing against: <strong>{dpdpState.selectedBaseline.file_name}</strong>
              </div>
            )}

            {/* Delete confirmation dialog */}
            {deleteConfirm && (
              <div className="baseline-confirm-overlay">
                <div className="baseline-confirm-dialog">
                  <p className="baseline-confirm-msg">
                    Permanently delete '<strong>{deleteConfirm.file_name}</strong>'? This cannot be undone.
                  </p>
                  <div className="baseline-confirm-actions">
                    <button className="baseline-confirm-cancel" onClick={() => setDeleteConfirm(null)}>Cancel</button>
                    <button className="baseline-confirm-delete" onClick={() => handleDeleteBaseline(deleteConfirm)}>Delete</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="w-full bg-[#2F2F2F] py-3 flex-shrink-0">
        <div className="max-w-[1200px] mx-auto px-5 flex items-center justify-between">
          <p className="text-white/35 text-[11px] font-medium">&copy; 2026 South Indian Bank. All rights reserved.</p>
        </div>
      </footer>
    </>
  );
}
