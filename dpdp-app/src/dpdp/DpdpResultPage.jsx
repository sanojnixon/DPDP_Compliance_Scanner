import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import PageShell from './PageShell';
import { useDpdpStore } from './useDpdpStore.jsx';
import './dpdp.css';

// ── Colour helpers ────────────────────────────────────────────────────────────
const RISK_COLOR   = { Critical: '#DC2626', High: '#D97706', Medium: '#2563EB', Low: '#16A34A', None: '#6B7280' };
const RISK_BG      = { Critical: '#FEF2F2', High: '#FFFBEB', Medium: '#EFF6FF', Low: '#F0FDF4', None: '#F3F4F6' };
const RISK_BORDER  = { Critical: '#FECACA', High: '#FDE68A', Medium: '#BFDBFE', Low: '#BBF7D0', None: '#E5E7EB' };

function confColor(s) {
  if (s >= 0.90) return '#16A34A';
  if (s >= 0.75) return '#CA8A04';
  return '#DC2626';
}

// ── Confidence computation ────────────────────────────────────────────────────
function computeConfidence({ ocr, entities, ai, verdict }) {
  // OCR average confidence (40% weight)
  const ocrConf = typeof ocr?.avg_confidence === 'number' ? ocr.avg_confidence : null;

  // Entity average confidence (30% weight)
  const entityConf = entities?.length > 0
    ? entities.reduce((s, e) => s + (e.confidence || 0), 0) / entities.length
    : null;

  // AI reasoning confidence — use violation avg confidence if present (20% weight)
  let aiConf = null;
  const violations = verdict?.violation_details || [];
  if (violations.length > 0) {
    aiConf = violations.reduce((s, v) => s + (v.confidence || 0.7), 0) / violations.length;
  } else if (ai?.status === 'success') {
    aiConf = 0.85; // AI succeeded but found no violations
  }

  // Rule certainty (10% weight) — evaluated/applicable ratio
  const evaluated = verdict?.rules_evaluated?.length || 0;
  const ruleConf = evaluated > 0 ? Math.min(1, evaluated / 26) : null;

  // Weighted combination of available signals
  let totalWeight = 0, totalScore = 0;
  if (ocrConf !== null)    { totalScore += ocrConf    * 0.40; totalWeight += 0.40; }
  if (entityConf !== null) { totalScore += entityConf * 0.30; totalWeight += 0.30; }
  if (aiConf !== null)     { totalScore += aiConf     * 0.20; totalWeight += 0.20; }
  if (ruleConf !== null)   { totalScore += ruleConf   * 0.10; totalWeight += 0.10; }

  if (totalWeight === 0) return null;
  return Math.round((totalScore / totalWeight) * 100);
}


// ── Risk Badge ────────────────────────────────────────────────────────────────
function RiskBadge({ risk }) {
  return (
    <span className="pii-risk-badge" style={{
      color: RISK_COLOR[risk] || '#6B7280',
      background: RISK_BG[risk] || '#F9FAFB',
      border: `1px solid ${RISK_BORDER[risk] || '#E5E7EB'}`,
    }}>
      {risk}
    </span>
  );
}

// ── Single PII Entity Row ─────────────────────────────────────────────────────
function EntityRow({ entity, index }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`pii-entity-row ${open ? 'expanded' : ''}`}>
      <div className="pii-entity-header" onClick={() => setOpen(o => !o)}>
        <span className="pii-entity-idx">#{index + 1}</span>
        <div className="pii-entity-main">
          <span className="pii-entity-type">{entity.type}</span>
          <span className="pii-entity-val">{entity.value}</span>
        </div>
        <RiskBadge risk={entity.risk} />
        <span className="pii-entity-conf" style={{ color: confColor(entity.confidence) }}>
          {Math.round(entity.confidence * 100)}%
        </span>
        {entity.masked && <span className="pii-masked-tag">Masked</span>}
        <svg className={`ocr-chevron ${open ? 'open' : ''}`} width="14" height="14"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {open && (
        <div className="pii-entity-detail">
          <div className="ocr-detail-row">
            <span className="ocr-detail-key">Category</span>
            <span className="ocr-detail-val">{entity.category}</span>
          </div>
          <div className="ocr-detail-row">
            <span className="ocr-detail-key">Detected value</span>
            <span className="ocr-detail-val" style={{ fontFamily: 'monospace' }}>{entity.value}</span>
          </div>
          <div className="ocr-detail-row">
            <span className="ocr-detail-key">Masked</span>
            <span className="ocr-detail-val">{entity.masked ? '✓ Yes' : '✗ No (exposed)'}</span>
          </div>
          <div className="ocr-detail-row">
            <span className="ocr-detail-key">Confidence</span>
            <span className="ocr-detail-val" style={{ color: confColor(entity.confidence) }}>
              {entity.confidence}
            </span>
          </div>
          {entity.bbox && (
            <div className="ocr-detail-row">
              <span className="ocr-detail-key">Bounding box</span>
              <span className="ocr-detail-val ocr-bbox">
                {entity.bbox.map(pt => `[${pt[0]}, ${pt[1]}]`).join(' → ')}
              </span>
            </div>
          )}
          {entity.ocr_block_indices?.length > 0 && (
            <div className="ocr-detail-row">
              <span className="ocr-detail-key">OCR block(s)</span>
              <span className="ocr-detail-val">#{entity.ocr_block_indices.join(', #')}</span>
            </div>
          )}
          {entity.document_type && (
            <div className="ocr-detail-row">
              <span className="ocr-detail-key">Document type</span>
              <span className="ocr-detail-val">{entity.document_type}</span>
            </div>
          )}
          {entity.source_rule && (
            <div className="ocr-detail-row">
              <span className="ocr-detail-key">Source Rule</span>
              <span className="ocr-detail-val">{entity.source_rule}</span>
            </div>
          )}
          {entity.reason && (
            <div className="ocr-detail-row">
              <span className="ocr-detail-key">Reason</span>
              <span className="ocr-detail-val" style={{ fontStyle: 'italic', color: '#4B5563' }}>{entity.reason}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Category Group ────────────────────────────────────────────────────────────
function CategoryGroup({ category, entities }) {
  const [open, setOpen] = useState(true);
  const maxRisk = ['Critical','High','Medium','Low'].find(r => entities.some(e => e.risk === r)) || 'Low';
  return (
    <div className="pii-cat-group">
      <div className="pii-cat-group-header" onClick={() => setOpen(o => !o)}>
        <div className="pii-cat-group-left">
          <span className="pii-cat-group-name">{category}</span>
          <span className="pii-cat-group-count">{entities.length}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <RiskBadge risk={maxRisk} />
          <svg className={`ocr-chevron ${open ? 'open' : ''}`} width="14" height="14"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </div>
      {open && (
        <div className="pii-cat-group-body">
          {entities.map((entity, i) => (
            <EntityRow key={i} entity={entity} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}



// ── DPDP Verdict Panel (new rules engine) ────────────────────────────────────
const SEV_COLOR = { CRITICAL: '#DC2626', HIGH: '#D97706', MEDIUM: '#2563EB', LOW: '#16A34A' };
const SEV_BG    = { CRITICAL: '#FEF2F2', HIGH: '#FFFBEB', MEDIUM: '#EFF6FF', LOW: '#F0FDF4' };
const SEV_BORDER= { CRITICAL: '#FECACA', HIGH: '#FDE68A', MEDIUM: '#BFDBFE', LOW: '#BBF7D0' };

function SeverityBadge({ severity }) {
  const s = (severity || 'LOW').toUpperCase();
  return (
    <span className="pii-risk-badge" style={{
      color: SEV_COLOR[s] || '#6B7280',
      background: SEV_BG[s] || '#F9FAFB',
      border: `1px solid ${SEV_BORDER[s] || '#E5E7EB'}`,
      fontWeight: 700, fontSize: '11px', letterSpacing: '0.04em',
    }}>{s}</span>
  );
}

function ViolationCard({ violation }) {
  return (
    <div className="dpdp-violation-card" style={{
      borderLeft: `4px solid ${SEV_COLOR[violation.severity] || '#6B7280'}`,
      background: '#FAFAFA', borderRadius: '8px', padding: '14px 16px',
      marginBottom: '10px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', flexWrap: 'wrap' }}>
        <span style={{
          background: '#EFF6FF', color: '#1D4ED8', padding: '2px 8px',
          borderRadius: '4px', fontSize: '11px', fontWeight: 700,
        }}>{violation.act_section}</span>
        <SeverityBadge severity={violation.severity} />
        {violation.category && (
          <span style={{
            background: '#F3F4F6', color: '#4B5563', padding: '2px 8px',
            borderRadius: '4px', fontSize: '11px', fontWeight: 600,
          }}>{violation.category}</span>
        )}
      </div>
      {violation.section_title && (
        <p style={{ margin: '0 0 6px', fontSize: '12px', color: '#6B7280', fontWeight: 600 }}>
          {violation.section_title}
        </p>
      )}
      <p style={{ margin: '0 0 8px', fontSize: '13.5px', color: '#1F2937', lineHeight: 1.5 }}>
        {violation.finding}
      </p>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
        {violation.pii_involved?.length > 0 && violation.pii_involved.map((pii, i) => (
          <span key={i} style={{
            background: '#FEF2F2', color: '#991B1B', padding: '2px 7px',
            borderRadius: '4px', fontSize: '11px', fontFamily: 'monospace',
          }}>{pii}</span>
        ))}
        {violation.penalty_reference && (
          <span style={{
            background: '#FFF7ED', color: '#9A3412', padding: '2px 7px',
            borderRadius: '4px', fontSize: '10px', fontWeight: 600,
            marginLeft: 'auto',
          }}>⚠ Penalty: {violation.penalty_reference}</span>
        )}
      </div>
    </div>
  );
}

function DpdpVerdictPanel({ verdict, aiAnalysis }) {
  if (!verdict) return <div className="ocr-no-text">DPDP Rules Engine evaluation not available.</div>;

  const violations = verdict.violation_details || [];
  const aiViolations = aiAnalysis?.violation_details || [];
  const verdictStatus = verdict.violations_found;

  // Merge: show deterministic violations first, then AI-only violations
  const detSections = new Set(violations.map(v => v.act_section));
  const aiOnly = aiViolations.filter(v => !detSections.has(v.act_section));
  const allViolations = [...violations, ...aiOnly];

  return (
    <div className="ai-analysis-wrap">
      {/* Verdict banner */}
      <div style={{
        padding: '14px 18px', borderRadius: '8px', marginBottom: '16px',
        background: verdictStatus === 'YES' ? '#FEF2F2' : verdictStatus === 'INCONCLUSIVE' ? '#FFFBEB' : '#F0FDF4',
        border: `1px solid ${verdictStatus === 'YES' ? '#FECACA' : verdictStatus === 'INCONCLUSIVE' ? '#FDE68A' : '#BBF7D0'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: '15px', color: '#1F2937' }}>DPDP Compliance Verdict</span>
          <div style={{ fontSize: '13px', color: '#4B5563', marginTop: '4px' }}>
            {verdict.rules_evaluated?.length || 0} compliance areas evaluated
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{
            fontWeight: 800, fontSize: '14px',
            color: verdictStatus === 'YES' ? '#DC2626' : verdictStatus === 'INCONCLUSIVE' ? '#D97706' : '#16A34A',
          }}>
            {verdictStatus === 'YES' ? '⚠ VIOLATIONS FOUND' : verdictStatus === 'INCONCLUSIVE' ? '⚡ INCONCLUSIVE' : '✓ NO VIOLATIONS'}
          </span>
          {verdict.overall_severity && <SeverityBadge severity={verdict.overall_severity} />}
        </div>
      </div>

      {/* Inconclusive notes */}
      {verdictStatus === 'INCONCLUSIVE' && verdict.notes?.length > 0 && (
        <div style={{
          background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: '8px',
          padding: '12px 16px', marginBottom: '14px', fontSize: '13px', color: '#92400E',
        }}>
          <strong>Inconclusive Conditions:</strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: '20px' }}>
            {verdict.notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      )}

      {/* Violation cards */}
      {allViolations.length === 0 ? (
        <div className="pii-no-flags">
          <span style={{ fontSize: '20px' }}>✓</span>
          All {verdict.rules_evaluated?.length || 0} applicable rules passed — including consent, minimisation, third-party, retention, and grievance checks.
        </div>
      ) : (
        <div>
          <span className="ai-section-title" style={{ marginBottom: '10px', display: 'block' }}>
            Violation Details ({allViolations.length})
          </span>
          {allViolations.map((v, i) => <ViolationCard key={i} violation={v} index={i} />)}
        </div>
      )}

      {/* PII Inventory summary */}
      {verdict.pii_inventory && (
        <div style={{ marginTop: '16px' }}>
          <span className="ai-section-title">PII Inventory Scan</span>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px' }}>
            {Object.entries(verdict.pii_inventory).filter(([,v]) => v === 'PRESENT').map(([k]) => (
              <span key={k} style={{
                background: '#FEF2F2', color: '#991B1B', padding: '3px 8px',
                borderRadius: '4px', fontSize: '11px', fontWeight: 600, fontFamily: 'monospace',
              }}>{k}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Full-text with PII highlighted ───────────────────────────────────────────
function AiFindingRow({ finding, index }) {
  return (
    <div className="ai-finding-row">
      <div className="ai-finding-head">
        <span className="pii-entity-idx">#{index + 1}</span>
        <div className="ai-finding-title-wrap">
          <span className="ai-finding-title">{finding.issue}</span>
          <span className="ai-finding-category">{finding.category || 'Screen-Level Risk'}</span>
        </div>
        <RiskBadge risk={finding.severity === 'Info' ? 'Low' : finding.severity} />
        <span className="ai-confidence">{Math.round((finding.confidence || 0) * 100)}%</span>
      </div>
      <div className="ai-finding-body">
        <div className="ocr-detail-row">
          <span className="ocr-detail-key">Why</span>
          <span className="ocr-detail-val">{finding.reason}</span>
        </div>
        {finding.supporting_ocr && (
          <div className="ocr-detail-row">
            <span className="ocr-detail-key">Evidence</span>
            <span className="ocr-detail-val">{finding.supporting_ocr}</span>
          </div>
        )}
        {finding.related_pii_entities?.length > 0 && (
          <div className="ocr-detail-row">
            <span className="ocr-detail-key">Related PII</span>
            <span className="ocr-detail-val">{finding.related_pii_entities.join(', ')}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function AiAnalysisPanel({ ai }) {
  if (!ai) return <div className="ocr-no-text">AI reasoning has not returned a result for this scan.</div>;

  const findings = ai.findings || [];
  const recommendations = ai.recommendations || [];
  const limitations = ai.limitations || [];

  return (
    <div className="ai-analysis-wrap">
      {ai.status === 'fallback' && (
        <div className="ai-fallback-banner">
          AI Vision was unavailable. Showing deterministic DPDP fallback analysis.
        </div>
      )}
      <div className="ai-summary-panel">
        <div className="ai-summary-copy">
          <span className="ai-kicker">AI Compliance Reasoning</span>
          <p className="ai-summary-text">{ai.ai_summary}</p>
        </div>
        <div className="ai-risk-stack">
          <RiskBadge risk={ai.overall_risk || 'Low'} />
          <span>{ai.screen_sensitivity || 'Low'} sensitivity</span>
        </div>
      </div>
      <div className="ai-purpose-card">
        <span className="ai-section-title">Purpose Limitation</span>
        <p>{ai.purpose_limitation?.assessment || 'No purpose limitation assessment available.'}</p>
        <span className={`ai-exposure-pill ${ai.purpose_limitation?.excessive_data_exposure ? 'risk' : 'ok'}`}>
          {ai.purpose_limitation?.excessive_data_exposure ? 'Excessive exposure likely' : 'No excess exposure flagged'}
        </span>
      </div>
      <div className="ai-section">
        <span className="ai-section-title">AI Findings</span>
        {findings.length === 0 ? (
          <div className="ocr-no-text">No AI compliance findings were generated.</div>
        ) : findings.map((finding, i) => (
          <AiFindingRow key={i} finding={finding} index={i} />
        ))}
      </div>
      <div className="ai-two-col">
        <div className="ai-list-card">
          <span className="ai-section-title">Recommendations</span>
          {recommendations.length === 0 ? (
            <p className="ai-muted">No AI recommendations available.</p>
          ) : (
            <ul className="ai-list">
              {recommendations.map((item, i) => <li key={i}>{item}</li>)}
            </ul>
          )}
        </div>
        <div className="ai-list-card">
          <span className="ai-section-title">Limitations</span>
          {limitations.length === 0 ? (
            <p className="ai-muted">No limitations reported.</p>
          ) : (
            <ul className="ai-list">
              {limitations.map((item, i) => <li key={i}>{item}</li>)}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function HighlightedText({ fullText, entities }) {
  if (!fullText) return <pre className="ocr-fulltext-body">(no text extracted)</pre>;

  // Build sorted list of ranges to highlight
  const ranges = [];
  for (const entity of entities) {
    const val = entity.value;
    let idx = 0;
    while (true) {
      const pos = fullText.indexOf(val, idx);
      if (pos === -1) break;
      ranges.push({ start: pos, end: pos + val.length, entity });
      idx = pos + val.length;
    }
  }
  ranges.sort((a, b) => a.start - b.start);

  const parts = [];
  let cursor = 0;
  for (const range of ranges) {
    if (range.start < cursor) continue; // overlap skip
    if (range.start > cursor) parts.push({ text: fullText.slice(cursor, range.start), entity: null });
    parts.push({ text: fullText.slice(range.start, range.end), entity: range.entity });
    cursor = range.end;
  }
  if (cursor < fullText.length) parts.push({ text: fullText.slice(cursor), entity: null });

  return (
    <pre className="ocr-fulltext-body pii-highlighted-text">
      {parts.map((part, i) =>
        part.entity ? (
          <mark key={i} className="pii-highlight"
            style={{
              background: RISK_BG[part.entity.risk] || '#FFF9C4',
              borderBottom: `2px solid ${RISK_COLOR[part.entity.risk] || '#CA8A04'}`,
            }}
            title={`${part.entity.type} — ${part.entity.risk} risk`}
          >
            {part.text}
          </mark>
        ) : (
          <span key={i}>{part.text}</span>
        )
      )}
    </pre>
  );
}

// ── OCR Block View (existing, minimal) ───────────────────────────────────────
function OcrBlockView({ ocr }) {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState('blocks');

  const handleCopy = () => {
    navigator.clipboard.writeText(ocr.full_text || '').then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <>
      <div className="ocr-view-toggle" style={{ marginBottom: '14px' }}>
        <button className={`ocr-toggle-btn ${viewMode === 'blocks' ? 'active' : ''}`}
          onClick={() => setViewMode('blocks')} id="view-blocks-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
            <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
          </svg>
          Block View
        </button>
        <button className={`ocr-toggle-btn ${viewMode === 'fulltext' ? 'active' : ''}`}
          onClick={() => setViewMode('fulltext')} id="view-fulltext-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/>
            <line x1="4" y1="18" x2="14" y2="18"/>
          </svg>
          Full Text
        </button>
      </div>

      {viewMode === 'blocks' && (
        <div className="ocr-blocks-container">
          {(ocr.blocks || []).length === 0
            ? <div className="ocr-no-text">No text blocks extracted.</div>
            : (ocr.blocks || []).map((block, i) => (
              <div key={i} className="ocr-block">
                <div className="ocr-block-header" style={{ cursor: 'default' }}>
                  <div className="ocr-block-index">#{i + 1}</div>
                  <div className="ocr-block-text-preview">{block.text}</div>
                  <div className="ocr-block-conf" style={{ color: confColor(block.confidence) }}>
                    {Math.round(block.confidence * 100)}%
                  </div>
                </div>
                <div className="ocr-conf-bar-track">
                  <div className="ocr-conf-bar-fill"
                    style={{ width: `${Math.round(block.confidence * 100)}%`, background: confColor(block.confidence) }} />
                </div>
              </div>
            ))
          }
        </div>
      )}

      {viewMode === 'fulltext' && (
        <div className="ocr-fulltext-card">
          <div className="ocr-fulltext-header">
            <span className="ocr-fulltext-title">Extracted Full Text</span>
            <button className="ocr-copy-btn" onClick={handleCopy} id="ocr-copy-btn">
              {copied ? '✓ Copied' : 'Copy'}
            </button>
          </div>
          <pre className="ocr-fulltext-body">{ocr.full_text || '(empty)'}</pre>
        </div>
      )}
    </>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function DpdpResultPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, dispatch } = useDpdpStore();

  // Accept pre-loaded results when navigating back from ROPA page
  const preloaded = location.state?.scanResults || [];

  const [scanResults, setScanResults] = useState(preloaded);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeImage, setActiveImage] = useState(0);
  const [activeTab, setActiveTab] = useState('verdict');

  // Dev Tools state
  const devMode = state.devMode;
  const selectedBaseline = state.selectedBaseline;
  const [checkedRules, setCheckedRules] = useState({});
  const [baselineName, setBaselineName] = useState('');
  const [baselineSaving, setBaselineSaving] = useState(false);
  const [toastMsg, setToastMsg] = useState('');
  const [toastVisible, setToastVisible] = useState(false);

  // Baseline comparison state
  const [comparisonResults, setComparisonResults] = useState(null); // { rule_id, status, finding }[]

  const token = localStorage.getItem('token');
  const imageIds = state.imageIds;

  const runScan = useCallback(async () => {
    if (!imageIds?.length) return;
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(
        imageIds.map(id =>
          fetch(`http://localhost:5000/api/pii/${id}`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
          }).then(r => {
            if (!r.ok) throw new Error(`Scan failed for image ${id} (HTTP ${r.status})`);
            return r.json();
          })
        )
      );
      setScanResults(results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [imageIds, token]);

  // Only run scan if we don't have pre-loaded results from ROPA back-navigation
  useEffect(() => { if (!preloaded.length) runScan(); }, []); // eslint-disable-line

  // ── Baseline comparison: runs AFTER scanResults are populated ──
  useEffect(() => {
    if (!selectedBaseline || scanResults.length === 0) return;
    const tkn = localStorage.getItem('token');
    if (!tkn) return;

    (async () => {
      try {
        // Fetch the full baseline record (including JSONB payload)
        const res = await fetch(`http://localhost:5000/api/dev/baseline/${selectedBaseline.id}`, {
          headers: { Authorization: `Bearer ${tkn}` },
        });
        if (!res.ok) return;
        const baseline = await res.json();
        const expectedRules = baseline.payload?.corrections_expected || [];
        if (expectedRules.length === 0) { setComparisonResults([]); return; }

        // Collect all violations from the NEW scan across all images
        const newViolations = [];
        for (const result of scanResults) {
          for (const v of (result.dpdp_verdict?.violation_details || [])) {
            newViolations.push(v);
          }
          for (const v of (result.ai_analysis?.violation_details || [])) {
            newViolations.push(v);
          }
        }

        // Compare each expected correction against the new scan
        const results = expectedRules.map(ruleId => {
          const found = newViolations.find(
            v => (v.rule_id || v.act_section) === ruleId
          );
          return {
            rule_id: ruleId,
            status: found ? 'still_present' : 'corrected',
            finding: found ? found.finding : null,
          };
        });

        setComparisonResults(results);
      } catch (e) {
        console.error('Baseline comparison failed:', e);
      }
    })();
  }, [selectedBaseline, scanResults]); // eslint-disable-line

  const handleStartOver = () => {
    dispatch({ type: 'RESET' });
    navigate('/select');
  };

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <PageShell currentStep={2} totalSteps={2}>
        <div className="ocr-loading-card">
          <div className="ocr-spinner" />
          <h2 className="ocr-loading-title">Running DPDP Compliance Scan…</h2>
          <p className="ocr-loading-subtitle">
            OCR is extracting text and the PII detection engine is classifying entities.
            This may take a moment on the first run while model weights load.
          </p>
        </div>
      </PageShell>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <PageShell currentStep={2} totalSteps={2}>
        <div className="ocr-error-card">
          <div className="ocr-error-icon">⚠</div>
          <h2 className="ocr-error-title">Scan Failed</h2>
          <p className="ocr-error-msg">{error}</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '24px' }}>
            <button className="ocr-retry-btn" id="scan-retry-btn" onClick={runScan}>Retry</button>
            <button className="ocr-back-btn" id="scan-back-btn" onClick={handleStartOver}>Back to Tools</button>
          </div>
        </div>
      </PageShell>
    );
  }

  // ── No images ──────────────────────────────────────────────────────────────
  if (!imageIds?.length) {
    return (
      <PageShell currentStep={2} totalSteps={2}>
        <div className="ocr-error-card">
          <div className="ocr-error-icon" style={{ color: '#CA8A04' }}>⚠</div>
          <h2 className="ocr-error-title">No Images to Scan</h2>
          <p className="ocr-error-msg">Upload a document and restart the scan flow.</p>
          <button className="ocr-back-btn" style={{ marginTop: '24px' }} onClick={handleStartOver}>
            Back to Analysis Tools
          </button>
        </div>
      </PageShell>
    );
  }

  const current = scanResults[activeImage];
  const entities = current?.entities || [];
  const compliance = current?.compliance || {};
  const ocr = current?.ocr || {};
  const ai = current?.ai_analysis || {};
  const verdict = current?.dpdp_verdict || null;

  // Group entities by category
  const byCategory = {};
  for (const e of entities) {
    if (!byCategory[e.category]) byCategory[e.category] = [];
    byCategory[e.category].push(e);
  }
  // Sort categories by highest risk first
  const riskOrder = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  const sortedCategories = Object.keys(byCategory).sort((a, b) => {
    const aRisk = Math.min(...byCategory[a].map(e => riskOrder[e.risk] ?? 4));
    const bRisk = Math.min(...byCategory[b].map(e => riskOrder[e.risk] ?? 4));
    return aRisk - bRisk;
  });

  return (
    <PageShell currentStep={2} totalSteps={2} centered={false}>
      <div className="ocr-results-layout">

        {/* ── Left Main Panel ── */}
        <div className="ocr-results-main">

          {/* Summary banner */}
          <div className="ocr-summary-banner">
            <div className="ocr-summary-item">
              <span className="ocr-summary-val" style={{
                color: verdict?.violations_found === 'YES' ? '#DC2626' : verdict?.violations_found === 'INCONCLUSIVE' ? '#D97706' : '#16A34A',
                fontSize: '13px', fontWeight: 800,
              }}>
                {verdict?.violations_found || '—'}
              </span>
              <span className="ocr-summary-key">Verdict</span>
            </div>
            <div className="ocr-summary-divider" />
            <div className="ocr-summary-item">
              <span className="ocr-summary-val">{verdict?.violation_details?.length || 0}</span>
              <span className="ocr-summary-key">Violations</span>
            </div>
            <div className="ocr-summary-divider" />
            <div className="ocr-summary-item">
              <span className="ocr-summary-val">{entities.length}</span>
              <span className="ocr-summary-key">PII Entities</span>
            </div>
            <div className="ocr-summary-divider" />
            <div className="ocr-summary-item">
              {(() => {
                const conf = computeConfidence({ ocr, entities, ai, verdict });
                return (
                  <>
                    <span className="ocr-summary-val" style={{
                      color: conf !== null ? confColor(conf / 100) : '#6B7280',
                      fontSize: conf !== null ? '16px' : '12px',
                      fontWeight: 800,
                    }}>
                      {conf !== null ? `${conf}%` : 'Pending'}
                    </span>
                    <span className="ocr-summary-key">Confidence Level</span>
                  </>
                );
              })()}
            </div>
          </div>

          {/* Risk distribution bar */}
          {entities.length > 0 && (
            <div className="pii-risk-row">
              {['Critical','High','Medium','Low'].map(r => (
                <div key={r} className="pii-risk-count-chip"
                  style={{ color: RISK_COLOR[r], background: RISK_BG[r], border: `1px solid ${RISK_BORDER[r]}` }}>
                  <strong>{compliance.by_risk?.[r] || 0}</strong> {r}
                </div>
              ))}
            </div>
          )}

          {/* Image tabs (multi-image support) */}
          {scanResults.length > 1 && (
            <div className="ocr-tabs">
              {scanResults.map((r, i) => (
                <button key={i}
                  className={`ocr-tab ${i === activeImage ? 'active' : ''}`}
                  onClick={() => setActiveImage(i)}
                  id={`img-tab-${i}`}>
                  {r.filename || `Image ${i + 1}`}
                </button>
              ))}
            </div>
          )}

          {/* View tabs */}
          <div className="pii-view-tabs">
            {[
              { key: 'verdict', label: `⚖ DPDP Verdict (${verdict?.violation_details?.length || 0})` },
              { key: 'ai',      label: `AI Reasoning (${ai.findings?.length || 0})` },
              { key: 'pii',     label: '🔍 PII Analysis' },
              { key: 'ocr',     label: '📄 OCR Text' },
              ...(devMode ? [{ key: 'devtools', label: '🛠 Dev Tools' }] : []),
            ].map(({ key, label }) => (
              <button key={key}
                className={`pii-view-tab ${activeTab === key ? 'active' : ''}`}
                onClick={() => setActiveTab(key)}
                id={`tab-${key}`}>
                {label}
              </button>
            ))}
          </div>

          {/* ── DPDP Verdict Tab ── */}
          {activeTab === 'verdict' && (
            <div className="pii-analysis-panel">
              <DpdpVerdictPanel verdict={verdict} aiAnalysis={ai} />
            </div>
          )}

          {/* ── PII Analysis Tab ── */}
          {activeTab === 'pii' && (
            <div className="pii-analysis-panel">
              {entities.length === 0 ? (
                <div className="ocr-no-text">
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>✓</div>
                  No PII detected in this document.
                </div>
              ) : (
                sortedCategories.map(cat => (
                  <CategoryGroup key={cat} category={cat} entities={byCategory[cat]} />
                ))
              )}
            </div>
          )}

          {/* ── Flags Tab ── */}
          {activeTab === 'ai' && (
            <div className="pii-analysis-panel">
              <AiAnalysisPanel ai={ai} />
            </div>
          )}



          {/* ── OCR Tab ── */}
          {activeTab === 'ocr' && (
            <div className="pii-analysis-panel">
              <OcrBlockView ocr={ocr} />
            </div>
          )}

          {/* ── Dev Tools Tab ── */}
          {activeTab === 'devtools' && devMode && (() => {
            // Merge & deduplicate violations by rule_id
            const detViolations = verdict?.violation_details || [];
            const aiViolations = ai?.violation_details || [];
            const seen = new Set();
            const merged = [];
            for (const v of [...detViolations, ...aiViolations]) {
              const rid = v.rule_id || v.act_section || `ai-${merged.length}`;
              if (!seen.has(rid)) {
                seen.add(rid);
                merged.push({ ...v, _ruleId: rid });
              }
            }

            const handleToggleRule = (ruleId) => {
              setCheckedRules(prev => ({ ...prev, [ruleId]: !prev[ruleId] }));
            };

            const showToast = (msg) => {
              setToastMsg(msg);
              setToastVisible(true);
              setTimeout(() => setToastVisible(false), 3500);
            };

            const handleSaveBaseline = async () => {
              if (!baselineName.trim()) return;
              setBaselineSaving(true);
              try {
                const images = scanResults.map(r => ({
                  filename: r.filename,
                  ocr: r.ocr,
                  entities: r.entities,
                  compliance: r.compliance,
                  dpdp_verdict: r.dpdp_verdict,
                  ai_analysis: r.ai_analysis,
                  candidate_entities: r.candidate_entities,
                  semantic_resolution: r.semantic_resolution,
                }));
                const corrections_expected = Object.entries(checkedRules)
                  .filter(([, v]) => v)
                  .map(([k]) => k);
                const resp = await fetch('http://localhost:5000/api/dev/baseline', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                  },
                  body: JSON.stringify({
                    file_name: baselineName.trim(),
                    payload: { images, corrections_expected },
                  }),
                });
                if (!resp.ok) {
                  const errorData = await resp.json().catch(() => ({}));
                  throw new Error(errorData.detail || `HTTP ${resp.status}`);
                }
                showToast(`Baseline '${baselineName.trim()}' saved.`);
                setBaselineName('');
              } catch (err) {
                showToast(`Error: ${err.message}`);
              } finally {
                setBaselineSaving(false);
              }
            };

            return (
              <div className="pii-analysis-panel devtools-panel">

                {/* ── Correction Verification (baseline comparison) ── */}
                {comparisonResults && comparisonResults.length > 0 && (
                  <>
                    <div className="devtools-section">
                      <span className="devtools-section-title">Correction Verification</span>
                      <p className="devtools-section-subtitle">
                        Comparing against baseline: <strong>{selectedBaseline?.file_name}</strong>
                      </p>
                      <div className="correction-verification-table">
                        <div className="correction-table-header">
                          <span className="correction-col-rule">Rule ID</span>
                          <span className="correction-col-status">Status</span>
                          <span className="correction-col-finding">Finding (new scan)</span>
                        </div>
                        {comparisonResults.map(cr => (
                          <div key={cr.rule_id} className={`correction-table-row ${cr.status}`}>
                            <span className="correction-col-rule">
                              <span className="devtools-rule-id">{cr.rule_id}</span>
                            </span>
                            <span className="correction-col-status">
                              <span className={`correction-badge ${cr.status}`}>
                                {cr.status === 'corrected' ? '✅ Corrected' : '❌ Still present'}
                              </span>
                            </span>
                            <span className="correction-col-finding">
                              {cr.finding || <span className="correction-no-finding">—</span>}
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="correction-summary">
                        <span className="correction-summary-stat corrected">
                          {comparisonResults.filter(r => r.status === 'corrected').length} corrected
                        </span>
                        <span className="correction-summary-stat still-present">
                          {comparisonResults.filter(r => r.status === 'still_present').length} still present
                        </span>
                      </div>
                    </div>
                    <div className="devtools-divider" />
                  </>
                )}
                {comparisonResults && comparisonResults.length === 0 && selectedBaseline && (
                  <>
                    <div className="devtools-section">
                      <span className="devtools-section-title">Correction Verification</span>
                      <div className="devtools-empty">
                        <span style={{ fontSize: '20px' }}>ℹ</span>
                        Baseline '{selectedBaseline.file_name}' has no corrections marked for comparison.
                      </div>
                    </div>
                    <div className="devtools-divider" />
                  </>
                )}

                <div className="devtools-section">
                  <span className="devtools-section-title">Mark Violations to Correct</span>
                  <p className="devtools-section-subtitle">
                    Select violations that should be flagged as corrections when saving this baseline.
                  </p>
                  {merged.length === 0 ? (
                    <div className="devtools-empty">
                      <span style={{ fontSize: '20px' }}>✓</span>
                      No violations detected in this scan — nothing to mark.
                    </div>
                  ) : (
                    <div className="devtools-checklist">
                      {merged.map(v => (
                        <label key={v._ruleId} className="devtools-check-row" htmlFor={`dev-check-${v._ruleId}`}>
                          <input
                            type="checkbox"
                            id={`dev-check-${v._ruleId}`}
                            checked={!!checkedRules[v._ruleId]}
                            onChange={() => handleToggleRule(v._ruleId)}
                            className="devtools-checkbox"
                          />
                          <span className="devtools-rule-id">{v._ruleId}</span>
                          <SeverityBadge severity={v.severity} />
                          <span className="devtools-finding">{v.finding}</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>

                <div className="devtools-divider" />

                <div className="devtools-section">
                  <label className="devtools-input-label" htmlFor="baseline-name">Baseline file name</label>
                  <div className="devtools-save-row">
                    <input
                      id="baseline-name"
                      type="text"
                      className="devtools-input"
                      placeholder="e.g. txn_history_baseline_v1"
                      value={baselineName}
                      onChange={e => setBaselineName(e.target.value)}
                    />
                    <button
                      id="save-baseline-btn"
                      className="devtools-save-btn"
                      disabled={!baselineName.trim() || baselineSaving}
                      onClick={handleSaveBaseline}
                    >
                      {baselineSaving ? 'Saving…' : 'Save Baseline File'}
                    </button>
                  </div>
                </div>

                {/* Toast notification */}
                {toastVisible && (
                  <div className="devtools-toast">
                    {toastMsg}
                  </div>
                )}
              </div>
            );
          })()}

        </div>

        {/* ── Right Sidebar ── */}
        <div className="ocr-results-sidebar">


          {current && (
            <div className="ocr-config-card">
              <p className="ocr-config-title">AI Compliance Posture</p>
              <div className="ocr-config-row">
                <span className="ocr-config-key">Provider</span>
                <span className="ocr-config-val">{ai.provider || 'ai model'} ({ai.status || 'pending'})</span>
              </div>
              <div className="ocr-config-row">
                <span className="ocr-config-key">Overall risk</span>
                <span className="ocr-config-val">{ai.overall_risk || '—'}</span>
              </div>
              <div className="ocr-config-row">
                <span className="ocr-config-key">Readiness</span>
                <span className="ocr-config-val">{ai.risk_score?.readiness || '—'}</span>
              </div>
              <div className="ocr-config-row">
                <span className="ocr-config-key">Findings</span>
                <span className="ocr-config-val">{ai.findings?.length || 0}</span>
              </div>
            </div>
          )}

          {/* Highlighted full text extract */}
          {current && entities.length > 0 && ocr.full_text && (
            <div className="ocr-config-card">
              <p className="ocr-config-title">PII Highlighted Text</p>
              <HighlightedText fullText={ocr.full_text} entities={entities} />
            </div>
          )}

          {/* Scan configuration */}
          <div className="ocr-config-card">
            <p className="ocr-config-title">Scan Configuration</p>
            <div className="ocr-config-row">
              <span className="ocr-config-key">Document type</span>
              <span className="ocr-config-val">
                {state.isProcess === true ? 'Process' : 'Non-Process'}
              </span>
            </div>
            {state.isProcess && state.processType && (
              <div className="ocr-config-row">
                <span className="ocr-config-key">Process name</span>
                <span className="ocr-config-val">{state.processType}</span>
              </div>
            )}
            <div className="ocr-config-row">
              <span className="ocr-config-key">PII types mapped</span>
              <span className="ocr-config-val">{state.selectedPiis.length}</span>
            </div>
            <div className="ocr-config-row">
              <span className="ocr-config-key">Images scanned</span>
              <span className="ocr-config-val">{scanResults.length}</span>
            </div>
            <div className="ocr-config-row">
              <span className="ocr-config-key">Status</span>
              <span className="ocr-config-val" style={{ color: '#16A34A' }}>✓ Scan Complete</span>
            </div>
          </div>

          <button id="ropa-generate-btn"
            className="ocr-back-btn"
            style={{
              width: '100%',
              background: 'linear-gradient(135deg, #991B1B, #7F1D1D)',
              color: '#fff',
              border: 'none',
              fontWeight: 700,
            }}
            onClick={() => navigate('/dpdp/ropa', {
              state: {
                scanResults,
                selectedBaseline: selectedBaseline || null,
                processContext: {
                  processType: state.processType,
                  isProcess: state.isProcess,
                },
              },
            })}>
            📋 Generate ROPA
          </button>

          <button id="scan-start-over-btn" className="ocr-back-btn"
            onClick={handleStartOver} style={{ width: '100%' }}>
            ← Back to Analysis Tools
          </button>
        </div>

      </div>
    </PageShell>
  );
}
