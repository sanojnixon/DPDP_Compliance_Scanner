import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import PageShell from './PageShell';
import { useDpdpStore } from './useDpdpStore.jsx';
import './dpdp.css';

const CATEGORY_COLORS = [
  '#B01E23', '#2563EB', '#7C3AED', '#0891B2',
  '#059669', '#D97706', '#DC2626', '#0284C7',
  '#9333EA', '#16A34A', '#CA8A04', '#BE185D',
];

const PII_CATEGORIES = [
  {
    name: 'KYC Documents',
    items: ['PAN Details','Aadhaar Details','Passport Details','Voter ID','Driving Licence Details'],
  },
  {
    name: 'Identity Data',
    items: ['Name','Identification Number (Customer ID / Employee ID)','Photograph','Date of Birth','Gender','Location (Geo tagging / location tracking)','Property Details','Personal/Residential Address','Nationality','Spouse Name','Dependent Details','Insurance Details','Certificates (Birth, Marriage, Death)','Personal Email ID','Personal Phone Number','Signature','Utility Bills','Religion','Reservation Category','Ration Number','Caste Certificate'],
  },
  {
    name: 'Employment Data',
    items: ['Employee Name','Employee Email ID','Designation','Department','Office Address','Past Employment Details','Employment Certificate','Relieving Letter'],
  },
  {
    name: 'Educational Data',
    items: ['Marksheet','Qualification Details','Degree Certificate','Leaving Certificate','Professional Certifications'],
  },
  {
    name: 'Health Data',
    items: ['Medical Records and History','Physiological Health Condition','Blood Group','Behavioral Characteristics','Health/Medical Reports'],
  },
  {
    name: 'Biometric Data',
    items: ['Fingerprints','Voice Patterns'],
  },
  {
    name: 'Online Identifiers',
    items: ['Username','Passwords','IP Address','Cookie Details','Browsing Patterns'],
  },
  {
    name: 'Children and Person with Disability Data',
    items: ['Child Name','Child Date of Birth','Guardian Name','Gender','Age','Nationality','Disability Status','Disability Certificate'],
  },
  {
    name: 'Financial Data',
    items: ['Bank Account Numbers','Debit Card Details','Credit Card Details','Credit Score','Bank Statements','UPI Handles','Account Balance','Account Transaction History','Income Proofs','Salary Slips','Income Certificate','Form 16','Tax Returns','CTC Data'],
  },
  {
    name: 'Social Media Data',
    items: ['LinkedIn Account Details','Facebook Account Details','WhatsApp Number','Instagram Account Details','Twitter Handle','Other Social Media Information'],
  },
  {
    name: 'Other Information',
    items: ['Voice Recording','Video Recording','CCTV Surveillance Recordings'],
  },
];

// Flat list of ALL built-in PII items for global ops
const ALL_BUILTIN_PIIS = PII_CATEGORIES.flatMap(c => c.items);

function CheckIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  );
}

function CategoryAccordion({ category, color, selectedPiis, onToggle, onSelectAll, onClearAll }) {
  const [open, setOpen] = useState(false);
  const selectedInCategory = category.items.filter(item => selectedPiis.includes(item)).length;
  const allInCategorySelected = selectedInCategory === category.items.length;

  const handleHeaderClick = (e) => {
    // Don't toggle accordion if clicking the action buttons
    if (e.target.closest('.pii-cat-actions')) return;
    setOpen(o => !o);
  };

  const handleSelectAll = (e) => {
    e.stopPropagation();
    onSelectAll(category.items);
    setOpen(true); // expand so user sees the change
  };

  const handleClear = (e) => {
    e.stopPropagation();
    onClearAll(category.items);
  };

  return (
    <div className="pii-category">
      <div className="pii-category-header" onClick={handleHeaderClick} role="button" aria-expanded={open}>
        <div className="pii-category-title-group">
          <div className="pii-category-dot" style={{ background: color }} />
          <span className="pii-category-name">{category.name}</span>
          <span className={`pii-category-count ${selectedInCategory > 0 ? 'has-selected' : ''}`}>
            {selectedInCategory > 0 ? `${selectedInCategory}/${category.items.length}` : category.items.length}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Category-level action buttons */}
          <div className="pii-cat-actions" onClick={e => e.stopPropagation()}>
            <button
              className={`pii-cat-action-btn ${allInCategorySelected ? 'pii-cat-action-btn--muted' : ''}`}
              onClick={handleSelectAll}
              title={`Select all in ${category.name}`}
              disabled={allInCategorySelected}
            >
              All
            </button>
            <button
              className={`pii-cat-action-btn pii-cat-action-btn--clear ${selectedInCategory === 0 ? 'pii-cat-action-btn--muted' : ''}`}
              onClick={handleClear}
              title={`Clear all in ${category.name}`}
              disabled={selectedInCategory === 0}
            >
              Clear
            </button>
          </div>

          <svg className={`pii-chevron ${open ? 'open' : ''}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </div>
      </div>

      <div className={`pii-category-items ${open ? 'open' : ''}`}>
        <div className="pii-items-grid">
          {category.items.map(item => {
            const checked = selectedPiis.includes(item);
            return (
              <div
                key={item}
                className="pii-item-row"
                onClick={() => onToggle(item)}
                role="checkbox"
                aria-checked={checked}
                tabIndex={0}
                onKeyDown={e => e.key === ' ' && onToggle(item)}
              >
                <div className={`pii-checkbox ${checked ? 'checked' : ''}`}>
                  {checked && <CheckIcon />}
                </div>
                <span className="pii-item-label">{item}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function PiiSelectionPage() {
  const navigate = useNavigate();
  const { state, dispatch } = useDpdpStore();
  const [customInput, setCustomInput] = useState('');

  const allSelected = [...state.selectedPiis];
  const totalBuiltinItems = ALL_BUILTIN_PIIS.length;
  const builtinSelectedCount = allSelected.filter(p => ALL_BUILTIN_PIIS.includes(p)).length;
  const isAllSelected = builtinSelectedCount === totalBuiltinItems;
  const isNoneSelected = allSelected.length === 0;

  // ── Individual toggle ──
  const handleToggle = useCallback((item) => dispatch({ type: 'TOGGLE_PII', payload: item }), [dispatch]);

  // ── Category-level: select all items in one category ──
  const handleCategorySelectAll = useCallback((items) => {
    dispatch({ type: 'SELECT_MANY', payload: items });
  }, [dispatch]);

  // ── Category-level: clear all items in one category ──
  const handleCategoryClear = useCallback((items) => {
    dispatch({ type: 'DESELECT_MANY', payload: items });
  }, [dispatch]);

  // ── Global: select ALL built-in PIIs ──
  const handleGlobalSelectAll = useCallback(() => {
    dispatch({ type: 'SELECT_MANY', payload: ALL_BUILTIN_PIIS });
  }, [dispatch]);

  // ── Global: clear ALL selected PIIs (built-in + custom) ──
  const handleGlobalClearAll = useCallback(() => {
    dispatch({ type: 'CLEAR_ALL' });
  }, [dispatch]);

  const handleAddCustom = () => {
    if (!customInput.trim()) return;
    dispatch({ type: 'ADD_CUSTOM_PII', payload: customInput });
    setCustomInput('');
  };

  const handleRemoveCustom = (item) => dispatch({ type: 'REMOVE_CUSTOM_PII', payload: item });

  const handleRemoveSelected = (item) => {
    if (state.customPiis.includes(item)) {
      dispatch({ type: 'REMOVE_CUSTOM_PII', payload: item });
    } else {
      dispatch({ type: 'TOGGLE_PII', payload: item });
    }
  };

  const handleProceed = () => {
    if (allSelected.length === 0) return;
    navigate('/dpdp/result');
  };

  return (
    <PageShell currentStep={2} totalSteps={2}>
      <div className="pii-layout">

        {/* Left: Categories */}
        <div className="pii-panel">
          <div className="pii-panel-header">
            <div className="pii-panel-header-row">
              <div>
                <p className="pii-panel-title">Select PII Categories</p>
                <p className="pii-panel-subtitle">
                  Check all personally identifiable information types relevant to this document.
                </p>
              </div>

              {/* Global action buttons */}
              <div className="pii-global-actions">
                <button
                  id="pii-select-all-btn"
                  className={`pii-global-btn pii-global-btn--select ${isAllSelected ? 'pii-global-btn--disabled' : ''}`}
                  onClick={handleGlobalSelectAll}
                  disabled={isAllSelected}
                  title="Select all PIIs across all categories"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  Select All
                </button>
                <button
                  id="pii-clear-all-btn"
                  className={`pii-global-btn pii-global-btn--clear ${isNoneSelected ? 'pii-global-btn--disabled' : ''}`}
                  onClick={handleGlobalClearAll}
                  disabled={isNoneSelected}
                  title="Clear all selected PIIs"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  Clear All
                </button>
              </div>
            </div>
          </div>

          <div className="pii-categories">
            {PII_CATEGORIES.map((cat, i) => (
              <CategoryAccordion
                key={cat.name}
                category={cat}
                color={CATEGORY_COLORS[i % CATEGORY_COLORS.length]}
                selectedPiis={allSelected}
                onToggle={handleToggle}
                onSelectAll={handleCategorySelectAll}
                onClearAll={handleCategoryClear}
              />
            ))}
          </div>
        </div>

        {/* Right: Sidebar */}
        <div className="pii-sidebar">

          {/* Selected summary */}
          <div className="pii-summary-card">
            <p className="pii-summary-title">Selected PIIs</p>
            {allSelected.length === 0 ? (
              <p className="pii-empty-state">No PIIs selected yet. Check items on the left.</p>
            ) : (
              <div className="pii-selected-chips">
                {allSelected.map(item => (
                  <div key={item} className="pii-chip">
                    <span>{item}</span>
                    <button className="pii-chip-remove" onClick={() => handleRemoveSelected(item)} title="Deselect">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="pii-selected-count">
              <span>Total selected</span>
              <strong>{allSelected.length}</strong>
            </div>
          </div>

          {/* Custom PII */}
          <div className="pii-custom-card">
            <p className="pii-custom-title">Add Custom PII</p>
            <div className="pii-custom-input-row">
              <input
                id="custom-pii-input"
                type="text"
                className="pii-custom-input"
                placeholder="e.g. Vehicle Registration"
                value={customInput}
                onChange={e => setCustomInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAddCustom()}
              />
              <button id="custom-pii-add-btn" className="pii-custom-add-btn" onClick={handleAddCustom}>Add</button>
            </div>
            {state.customPiis.length > 0 && (
              <div className="pii-custom-chips">
                {state.customPiis.map(item => (
                  <div key={item} className="pii-custom-chip">
                    <span>{item}</span>
                    <button className="pii-custom-chip-remove" onClick={() => handleRemoveCustom(item)}>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Proceed */}
          <div className="pii-proceed-card">
            <button
              id="pii-proceed-btn"
              className="btn-primary"
              disabled={allSelected.length === 0}
              onClick={handleProceed}
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
                cursor: allSelected.length > 0 ? 'pointer' : 'not-allowed',
                opacity: allSelected.length > 0 ? 1 : 0.5,
                fontFamily: '\'Plus Jakarta Sans\', Arial, sans-serif',
              }}
            >
              Proceed with {allSelected.length} PII{allSelected.length !== 1 ? 's' : ''} →
            </button>
            {allSelected.length === 0 && (
              <p style={{ fontSize: '11px', color: '#9CA3AF', textAlign: 'center', marginTop: '8px', fontFamily: '\'Plus Jakarta Sans\', Arial, sans-serif' }}>
                Please select at least one PII to continue
              </p>
            )}
          </div>
        </div>

      </div>
    </PageShell>
  );
}
