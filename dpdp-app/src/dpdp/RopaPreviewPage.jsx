import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import PageShell from './PageShell';
import './ropa.css';

/* ── Section definitions matching Excel template ───────────────────────── */
const SECTIONS = [
  { id: 'general',    label: 'General Information' },
  { id: 'process',    label: 'Process Details' },
  { id: 'rights',     label: 'Rights & Decisions' },
  { id: 'processor',  label: 'Processor Info' },
  { id: 'transfer',   label: 'Data Transfer' },
  { id: 'storage',    label: 'Data Storage' },
  { id: 'dpia',       label: 'DPIA & Privacy' },
];

const FIELD_SECTION_MAP = {
  serial: 'general', department: 'general', spoc_name: 'general',
  application_name: 'general', process: 'general', purpose: 'general',
  description: 'process', data_principal_cats: 'process', includes_children: 'process',
  child_tracking: 'process', personal_data_cats: 'process', data_source: 'process',
  grounds: 'process', consent_type: 'process',
  automated_decisions: 'rights', data_principal_rights: 'rights',
  processor_name: 'processor', dpa_in_place: 'processor',
  third_party_safeguards: 'processor', other_recipients: 'processor',
  transfer_outside: 'transfer', transfer_country: 'transfer',
  transfer_purpose: 'transfer', transfer_safeguards: 'transfer',
  storage_format: 'storage', storage_location: 'storage',
  retention_period: 'storage', retention_purpose: 'storage',
  dpia_applicable: 'dpia', dpia_link: 'dpia', privacy_notice: 'dpia',
};

const FIELD_LABELS = {
  serial: '#', department: 'Department', spoc_name: 'SPOC Name',
  application_name: 'Application/Platform Name', process: 'Process',
  purpose: 'Purpose of processing', description: 'Description of data processing',
  data_principal_cats: 'Categories of Data Principals',
  includes_children: 'Includes children/disability?',
  child_tracking: 'Tracking/monitoring of children?',
  personal_data_cats: 'Categories of Personal Data processed',
  data_source: 'Source of personal data', grounds: 'Grounds for processing',
  consent_type: 'Consent type', automated_decisions: 'Automated decision making?',
  data_principal_rights: 'Rights of Data Principals',
  processor_name: 'Data processor(s)', dpa_in_place: 'DPA in place?',
  third_party_safeguards: 'Security safeguards (third parties)',
  other_recipients: 'Other recipients', transfer_outside: 'Transfer outside India?',
  transfer_country: 'Country of transfer', transfer_purpose: 'Purpose of transfer',
  transfer_safeguards: 'Transfer safeguards', storage_format: 'Storage format',
  storage_location: 'Storage location', retention_period: 'Retention period',
  retention_purpose: 'Purpose for retention', dpia_applicable: 'DPIA applicable?',
  dpia_link: 'DPIA record link', privacy_notice: 'Covered under Privacy Notice?',
};

const SOURCE_BADGES = {
  scan: { label: 'Scan', color: '#16A34A', bg: '#F0FDF4' },
  ai: { label: 'AI', color: '#7C3AED', bg: '#F5F3FF' },
  system: { label: 'System', color: '#6B7280', bg: '#F3F4F6' },
  manual: { label: 'Manual', color: '#D97706', bg: '#FFFBEB' },
};

function SourceBadge({ source }) {
  const s = SOURCE_BADGES[source] || SOURCE_BADGES.manual;
  return (
    <span className="ropa-source-badge" style={{ color: s.color, background: s.bg }}>
      {s.label}
    </span>
  );
}

function FieldCard({ fieldKey, value, source, warning, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || '');
  const label = FIELD_LABELS[fieldKey] || fieldKey;
  const isLong = ['description', 'data_principal_rights', 'third_party_safeguards',
    'personal_data_cats', 'purpose'].includes(fieldKey);

  const handleSave = () => {
    onUpdate(fieldKey, draft);
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft(value || '');
    setEditing(false);
  };

  return (
    <div className={`ropa-field-card ${warning ? 'ropa-field-warn' : ''} ${!value ? 'ropa-field-empty' : ''}`}>
      <div className="ropa-field-header">
        <span className="ropa-field-label">{label}</span>
        <div className="ropa-field-actions">
          <SourceBadge source={source} />
          {!editing && (
            <button className="ropa-edit-btn" onClick={() => setEditing(true)} title="Edit">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
          )}
        </div>
      </div>

      {editing ? (
        <div className="ropa-field-edit">
          {isLong ? (
            <textarea className="ropa-textarea" value={draft}
              onChange={e => setDraft(e.target.value)} rows={4} />
          ) : (
            <input className="ropa-input" value={draft}
              onChange={e => setDraft(e.target.value)} />
          )}
          <div className="ropa-edit-actions">
            <button className="ropa-save-btn" onClick={handleSave}>Save</button>
            <button className="ropa-cancel-btn" onClick={handleCancel}>Cancel</button>
          </div>
        </div>
      ) : (
        <div className="ropa-field-value">
          {value ? (
            <span className="ropa-value-text">{value}</span>
          ) : (
            <span className="ropa-value-empty">Not populated — requires manual input</span>
          )}
        </div>
      )}

      {warning && (
        <div className="ropa-field-warning">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          {warning}
        </div>
      )}
    </div>
  );
}

/* ── Completion Ring ─────────────────────────────────────────────────── */
function CompletionRing({ pct }) {
  const r = 38, cx = 46, cy = 46;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);
  const color = pct >= 80 ? '#16A34A' : pct >= 50 ? '#CA8A04' : '#DC2626';
  return (
    <div className="ropa-completion-ring">
      <svg width="92" height="92" viewBox="0 0 92 92">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#F3F4F6" strokeWidth="7" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="7"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 46 46)"
          style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
        <text x="46" y="43" textAnchor="middle" dominantBaseline="middle"
          fill={color} fontSize="18" fontWeight="800">{pct}%</text>
        <text x="46" y="58" textAnchor="middle" fill="#9CA3AF"
          fontSize="9" fontWeight="600">Complete</text>
      </svg>
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────────────────── */
export default function RopaPreviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const scanResults = location.state?.scanResults || [];
  const processContext = location.state?.processContext || {};

  const [ropaData, setRopaData] = useState(null);
  const [loading, setLoading] = useState(!!scanResults.length);
  const [error, setError] = useState(scanResults.length ? null : 'No scan results available. Run a DPDP scan first.');
  const [activeSection, setActiveSection] = useState('general');
  const [exporting, setExporting] = useState(false);
  const token = localStorage.getItem('token');
  // Store in ref so navigate(-1) can pass them back
  const scanState = { scanResults, processContext };

  /* Generate ROPA from scan results */
  useEffect(() => {
    if (!scanResults.length) return;
    (async () => {
      try {
        const res = await fetch('http://localhost:5000/api/ropa/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ scan_results: scanResults, process_context: processContext }),
        });
        if (!res.ok) throw new Error(`Server error ${res.status}`);
        const data = await res.json();
        setRopaData(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []); // eslint-disable-line

  /* Update a field */
  const handleUpdate = useCallback((key, value) => {
    setRopaData(prev => {
      if (!prev) return prev;
      const updated = {
        ...prev,
        ropa_entry: { ...prev.ropa_entry, [key]: value },
        source_map: { ...prev.source_map, [key]: 'manual' },
      };
      return updated;
    });
  }, []);

  /* Export as Excel */
  const handleExport = async () => {
    if (!ropaData) return;
    setExporting(true);
    try {
      const res = await fetch('http://localhost:5000/api/ropa/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          ropa_entries: [ropaData.ropa_entry],
          personal_data_inventory: ropaData.personal_data_inventory || {},
          metadata: { date: new Date().toISOString().split('T')[0] },
        }),
      });
      if (!res.ok) throw new Error(`Export failed (HTTP ${res.status})`);

      // Extract filename from Content-Disposition header if available
      const disposition = res.headers.get('Content-Disposition') || '';
      console.log('[Download Debug] Content-Disposition header:', disposition);

      const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/);
      let downloadName = filenameMatch ? filenameMatch[1] : 'SIB_DPDPA_Fiduciary_ROPA.xlsx';

      // 1. Clean the filename to ensure it has no carriage returns, quotes, or trailing control characters
      downloadName = downloadName.replace(/["']/g, '').replace(/[^a-zA-Z0-9_.-]/g, '').trim();

      // Safety fallback if it ends up empty
      if (!downloadName || downloadName.trim() === '') {
        downloadName = 'SIB_DPDPA_Fiduciary_ROPA.xlsx';
      }

      console.log('[Download Debug] Final explicit filename:', downloadName);

      const arrayBuf = await res.arrayBuffer();
      
      // 2. Use proper Excel MIME type
      const blob = new Blob([arrayBuf], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      
      console.log('[Download Debug] Blob created successfully, size:', blob.size);

      // 3. Bullet-proof modern download (File System Access API) - Supported in Chrome/Edge/Opera
      if (window.showSaveFilePicker) {
        try {
          console.log('[Download Debug] Using window.showSaveFilePicker');
          const fileHandle = await window.showSaveFilePicker({
            suggestedName: downloadName,
            types: [{
              description: 'Excel Spreadsheet',
              accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
            }],
          });
          const writable = await fileHandle.createWritable();
          await writable.write(blob);
          await writable.close();
          console.log('[Download Debug] File System Access API download complete');
          setExporting(false);
          return;
        } catch (err) {
          // If the user cancelled the dialog, we just exit. Otherwise fallback.
          if (err.name === 'AbortError') {
             console.log('[Download Debug] User cancelled file picker');
             setExporting(false);
             return;
          }
          console.error('[Download Debug] File System Access API failed, falling back to anchor:', err);
        }
      }

      // 4. Robust Anchor Fallback (Firefox, Safari, or if File System API fails)
      console.log('[Download Debug] Using anchor tag fallback');
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = downloadName;
      // Also try setting the attribute directly
      a.setAttribute('download', downloadName);

      document.body.appendChild(a);
      
      // Give the browser DOM a full tick to register the anchor element and its attributes
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          console.log('[Download Debug] Triggering anchor click for:', a.download);
          a.click();
          
          // 5. Keep the blob URL alive for 60 seconds to ensure the browser finishes initiating
          setTimeout(() => {
            if (document.body.contains(a)) {
              document.body.removeChild(a);
            }
            setTimeout(() => {
              window.URL.revokeObjectURL(url);
              console.log('[Download Debug] Blob URL revoked');
            }, 60000);
          }, 1000);
        });
      });
      
    } catch (e) {
      alert('Export failed: ' + e.message);
    } finally {
      setExporting(false);
    }
  };

  /* ── Loading state ───────────────────────────────────────────────── */
  if (loading) {
    return (
      <PageShell currentStep={2} totalSteps={2}>
        <div className="ropa-loading">
          <div className="ocr-spinner" />
          <h2>Generating ROPA…</h2>
          <p>Mapping scan findings to the Fiduciary ROPA template.</p>
        </div>
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell currentStep={2} totalSteps={2}>
        <div className="ropa-error">
          <div style={{ fontSize: 32 }}>⚠</div>
          <h2>ROPA Generation Failed</h2>
          <p>{error}</p>
          <button className="ocr-back-btn" onClick={() => navigate('/select')}>
            Back to Tools
          </button>
        </div>
      </PageShell>
    );
  }

  const entry = ropaData?.ropa_entry || {};
  const sourceMap = ropaData?.source_map || {};
  const validation = ropaData?.validation || {};
  const warnings = validation.warnings || [];
  const warningMap = {};
  warnings.forEach(w => { warningMap[w.field] = w.message; });

  /* Get fields for active section */
  const sectionFields = Object.keys(FIELD_SECTION_MAP)
    .filter(k => FIELD_SECTION_MAP[k] === activeSection);

  /* Count filled per section */
  const sectionFillCounts = {};
  SECTIONS.forEach(s => {
    const keys = Object.keys(FIELD_SECTION_MAP).filter(k => FIELD_SECTION_MAP[k] === s.id);
    const filled = keys.filter(k => entry[k]).length;
    sectionFillCounts[s.id] = { filled, total: keys.length };
  });

  return (
    <PageShell currentStep={2} totalSteps={2} centered={false}>
      <div className="ropa-layout">
        {/* Main panel */}
        <div className="ropa-main">
          <div className="ropa-title-bar">
            <div>
              <h1 className="ropa-title">Fiduciary ROPA Preview</h1>
              <p className="ropa-subtitle">
                Review and edit the auto-populated Record of Processing Activities
              </p>
            </div>
          </div>

          {/* Section tabs */}
          <div className="ropa-section-tabs">
            {SECTIONS.map(s => {
              const c = sectionFillCounts[s.id] || { filled: 0, total: 0 };
              return (
                <button key={s.id}
                  className={`ropa-section-tab ${activeSection === s.id ? 'active' : ''}`}
                  onClick={() => setActiveSection(s.id)}
                  id={`ropa-tab-${s.id}`}>
                  {s.label}
                  <span className="ropa-tab-count">{c.filled}/{c.total}</span>
                </button>
              );
            })}
          </div>

          {/* Field cards */}
          <div className="ropa-fields">
            {sectionFields.map(key => (
              <FieldCard key={key} fieldKey={key}
                value={entry[key]} source={sourceMap[key]}
                warning={warningMap[key]}
                onUpdate={handleUpdate} />
            ))}
          </div>
        </div>

        {/* Sidebar */}
        <div className="ropa-sidebar">
          <div className="ropa-sidebar-card" style={{ textAlign: 'center' }}>
            <CompletionRing pct={validation.completion_pct || 0} />
            <p className="ropa-sidebar-label">
              {validation.filled_count || 0} of {validation.total_count || 31} fields populated
            </p>
          </div>

          {warnings.length > 0 && (
            <div className="ropa-sidebar-card ropa-warnings-card">
              <p className="ropa-sidebar-title">
                ⚠ Validation ({warnings.length})
              </p>
              <div className="ropa-warnings-list">
                {warnings.slice(0, 6).map((w, i) => (
                  <div key={i} className="ropa-warning-item"
                    onClick={() => {
                      setActiveSection(FIELD_SECTION_MAP[w.field] || 'general');
                    }}>
                    <span className="ropa-warning-field">{w.header}</span>
                    <span className="ropa-warning-msg">{w.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="ropa-sidebar-card">
            <p className="ropa-sidebar-title">Source Breakdown</p>
            {['scan', 'ai', 'system', 'manual'].map(src => {
              const count = Object.values(sourceMap).filter(s => s === src).length;
              return (
                <div key={src} className="ropa-source-row">
                  <SourceBadge source={src} />
                  <span className="ropa-source-count">{count} fields</span>
                </div>
              );
            })}
          </div>

          <button className="ropa-export-btn" onClick={handleExport}
            disabled={exporting} id="ropa-download-btn">
            {exporting ? (
              <>
                <div className="ocr-spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                Exporting…
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                Download ROPA (.xlsx)
              </>
            )}
          </button>

          <button className="ocr-back-btn" style={{ width: '100%', marginTop: 8 }}
            onClick={() => navigate('/dpdp/result', { state: scanState })} id="ropa-back-btn">
            ← Back to Scan Report
          </button>
        </div>
      </div>
    </PageShell>
  );
}
