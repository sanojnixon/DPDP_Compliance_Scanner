# DPDP Compliance Scanner — LLM Handoff Document

> **Purpose:** Everything an LLM needs to understand the codebase, make changes, and implement new features without asking clarifying questions.

---

## Changelog

| Date | Description |
|------|-------------|
| 2026-06-03 | **Added baseline comparison workflow.** New `GET /api/dev/baseline` (list), `GET /api/dev/baseline/{id}` (full payload), and `DELETE /api/dev/baseline/{id}` (with ownership guard: 403/404) backend routes. Added `SELECTED_BASELINE` action to `useDpdpStore` (shape `{ id, file_name }`, initial `null`). `UploadPage.jsx` now shows a "Compare against baseline" section in dev mode: fetches baselines, shows radio-select list with delete buttons + confirmation dialog, stores selection in store. `DpdpResultPage.jsx` fetches the full baseline payload after scans complete, runs client-side comparison of `corrections_expected` rule IDs against new scan violations, and displays results in a "Correction Verification" table in the Dev Tools tab (✅ Corrected / ❌ Still present badges). ROPA flow is unaffected — `selectedBaseline` is passed via `location.state` but never touches ROPA generation. |
| 2026-06-03 | **Added Developer Mode toggle + Dev Tools tab.** New `DevModeToggle.jsx` component placed next to `DarkModeToggle` on every page header (LoginPage, UploadPage, SelectionPage, PageShell). State persisted in `localStorage('devMode')` and wired into `useDpdpStore` via `SET_DEV_MODE` action. When active, a fifth "Dev Tools" tab appears on `DpdpResultPage` with a violation correction checklist and baseline file save form that POSTs to `/api/dev/baseline`. |
| 2026-06-03 | **Added `dev_baselines` DB table and `/api/dev/baseline` route.** New `dev_baselines` table (JSONB payload) created in `lifespan()` startup. `POST /api/dev/baseline` accepts `{file_name, payload}` with JWT auth and inserts the baseline snapshot for regression testing. |
| 2026-06-02 | **Fixed second-scan 404 bug.** After a scan, image rows are deleted from the DB. Going back via the browser back button left stale image IDs in `location.state`; the next upload merged old (dead) IDs with new ones, causing 404 on the second scan. Fixed in `UploadPage.jsx` (no longer merges old IDs), `SelectionPage.jsx` (DPDP card uses `liveImageIds` derived from actual DB fetch, not stale `location.state`), and `ProcessPage.jsx` (always dispatches `RESET` before `SET_IMAGE_IDS`). |

---

## 1. Project Overview

**What it is:** A full-stack web application that audits Indian banking app screenshots for compliance with the **Digital Personal Data Protection (DPDP) Act, 2023**. Users upload screenshot images; the system OCRs them, detects PII entities, evaluates against ~26 DPDP rules, runs an AI reasoning pass, and produces a detailed compliance report plus an auto-generated ROPA (Record of Processing Activities) export.

**Primary domain:** Indian banking compliance. The scanner was built for South Indian Bank (SIB), which is why the ROPA template is labelled `SIB_DPDPA_Fiduciary_ROPA.xlsx`.

**Tech stack:**
| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite 8, React Router 7, Vanilla CSS |
| Backend | Python 3, FastAPI 0.110, asyncpg (PostgreSQL) |
| OCR | EasyOCR 1.7 (English + Hindi, CPU-only, lazy singleton) |
| AI Vision | OpenAI-compatible provider via `ai_providers.py` (generic, swappable) |
| AI Text / Audit | SambaNova chat-completions API via `services/ai_service.py` |
| Database | PostgreSQL 15 (via Docker) |
| Container | Docker Compose (`docker-compose.yml`) |

---

## 2. Repository Structure

```
project root/
├── backend/                  # FastAPI app (Python)
│   ├── main.py               # All API routes + app lifecycle
│   ├── dpdp_rules_engine.py  # 26-rule deterministic compliance checker
│   ├── dpdp_pii_registry.py  # PII ID taxonomy (PART A)
│   ├── dpdp_screen_classifier.py  # Screen type classifier (PART B)
│   ├── candidate_generator.py     # Regex + context candidate evidence
│   ├── entity_resolution.py       # Fuses deterministic + AI evidence
│   ├── ai_providers.py            # Swappable vision AI provider adapter
│   ├── ai_reasoning.py            # Vision AI prompt + call (multimodal)
│   ├── services/ai_service.py     # SambaNova text AI audit reasoning
│   ├── pii_patterns.py            # Regex patterns for PII detection
│   ├── pii_context.py             # Context-based entity extraction
│   ├── pii_classifier.py          # PII classification helpers
│   ├── pii_rules.py               # Legacy compliance report (deprecated)
│   ├── document_classifier.py     # OCR block → document type
│   ├── ocr_structure.py           # OCR blocks → lines/rows/columns
│   ├── layout_mapping.py          # Label-value spatial mapping
│   ├── banking_context.py         # Banking keyword detection
│   ├── aadhaar_validator.py       # Verhoeff checksum for Aadhaar
│   ├── entity_catalog.py          # DISPLAY_NAME / CATEGORY_MAP / RISK_MAP
│   ├── risk_scoring.py            # Risk score aggregation
│   ├── ropa_generator.py          # ROPA entry generation from scan
│   ├── ropa_export.py             # ROPA → Excel (openpyxl)
│   ├── prompt_formatter.py        # Prompt building helpers
│   ├── ocr_debug.py               # Debug overlay rendering
│   ├── patch_ocr.py               # OCR post-processing patches
│   ├── dpdp_act_sections.md       # DPDP Act reference (used by AI prompt)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env                       # API keys (gitignored)
│
├── dpdp-app/                 # React frontend (Vite)
│   └── src/
│       ├── App.jsx            # Router + DpdpProvider wrapper
│       ├── main.jsx           # Entry point
│       ├── LoginPage.jsx      # Auth page
│       ├── UploadPage.jsx     # Image upload + baseline comparison (dev mode)
│       ├── SelectionPage.jsx  # Tool selection hub
│       ├── ApkStatusPage.jsx  # APK scan job status page
│       ├── DarkModeToggle.jsx # Theme toggle component
│       ├── DevModeToggle.jsx  # Developer mode toggle (localStorage + store)
│       ├── index.css          # Global design tokens
│       ├── dpdp/
│       │   ├── useDpdpStore.jsx   # Global state (useReducer context)
│       │   ├── PageShell.jsx      # Shared layout shell with step progress
│       │   ├── ProcessPage.jsx    # Process type selection step
│       │   ├── PiiSelectionPage.jsx # PII type picker step
│       │   ├── DpdpResultPage.jsx # Main results dashboard (largest file)
│       │   ├── RopaPreviewPage.jsx# ROPA editor + export
│       │   ├── dpdp.css           # Result page + devtools + baseline styles
│       │   └── ropa.css           # ROPA page styles
│
├── rules_engine/
│   └── DPDP_Rules_Engine.md  # Authoritative rules spec (PARTS A–G)
├── directives/
│   └── brand_scraper.md
├── execution/
│   └── scrape_brand.py
├── docker-compose.yml
└── handoff.md                # This file
```

---

## 3. How to Run

### Docker (recommended)
```bash
docker-compose up --build
```
- Backend: `http://localhost:5000`
- Frontend: `http://localhost:5173`
- Database: `localhost:5432`

### Local development
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 5000

# Frontend
cd dpdp-app
npm install
npm run dev        # starts Vite on :5173 AND json-server on :3000
```

### Environment variables (`backend/.env`)
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/dpdp
JWT_SECRET=supersecret_dpdp_key
AI_API_KEY=<openai-compatible-vision-key>
AI_MODEL=<vision-model-name>
AI_BASE_URL=https://api.openai.com/v1
AI_TIMEOUT_SECONDS=45
SAMBANOVA_API_KEY=<sambanova-key>
SAMBANOVA_MODEL=<text-model-slug>
SAMBANOVA_BASE_URL=https://api.sambanova.ai/v1
SAMBANOVA_MAX_TOKENS=2048
SAMBANOVA_TEMPERATURE=0.1
SAMBANOVA_TIMEOUT_SECONDS=90
```

---

## 4. Backend API Routes

All routes require `Authorization: Bearer <jwt>` except `/api/login`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/login` | Returns JWT. Body: `{userId, password}` |
| `POST` | `/api/upload` | Upload images (multipart). Returns `{image_ids: [...]}` |
| `GET`  | `/api/images` | List user's stored images (optional `?ids=1,2,3`) |
| `DELETE` | `/api/images/{id}` | Delete an image |
| `POST` | `/api/ocr/{image_id}` | Run OCR on stored image. Returns blocks, lines, full text |
| `POST` | `/api/pii/{image_id}` | **Main scan endpoint.** Full pipeline: OCR → candidates → entity resolution → DPDP rules → AI audit. Deletes image after scan. |
| `POST` | `/api/ocr-debug` | Debug: upload image directly, returns annotated overlay. No AI call. |
| `POST` | `/api/analyze-ai` | Standalone AI text reasoning on a payload |
| `POST` | `/api/ropa/generate` | Generate ROPA entry from scan results array |
| `POST` | `/api/ropa/export` | Export ROPA entries as `.xlsx` blob |
| `POST` | `/api/dev/baseline` | Save baseline snapshot. Body: `{file_name, payload}` |
| `GET`  | `/api/dev/baseline` | List user's baselines (id, file_name, created_at) |
| `GET`  | `/api/dev/baseline/{id}` | Get single baseline with full JSONB payload |
| `DELETE` | `/api/dev/baseline/{id}` | Delete baseline (403 if not owner, 404 if not found) |

### Seeded users (hardcoded in `main.py` lifespan)
```
E1001 / Password123!
E1002 / Password123!
E1003 / Password123!
sanoj / sib123
admin / admin
```

---

## 5. The PII Detection Pipeline (`/api/pii/{image_id}`)

This is the core flow. Understanding it is critical for any change.

```
Image (DB) → OCR → OCR Structure → Document Classify
                                         ↓
                              Candidate Generator
                         (regex + context + layout)
                                         ↓
                           AI Vision Semantic Resolution
                         (analyze_entity_candidates)
                                         ↓
                              Entity Resolver
                          (fuse deterministic + AI)
                                         ↓
                          DPDP Rules Engine Evaluate
                                         ↓
                         AI Text Audit (SambaNova)
                                         ↓
                              JSON response
```

**Step-by-step:**

1. **OCR** (`_run_ocr_sync`): EasyOCR with `['en', 'hi']` languages. Hindi numerals (`०–९`) transliterated to ASCII. Rupee symbol (`₹`) restored via regex. Runs in thread pool executor.

2. **Structure** (`ocr_structure.parse_ocr_structure`): Groups OCR blocks into lines, rows, columns by spatial proximity.

3. **Document classify** (`document_classifier.classify_document`): Keyword heuristic → `"Bank Statement"`, `"KYC Form"`, `"Account Summary"`, etc.

4. **Candidate generation** (`candidate_generator.generate_entity_candidates`):
   - `pii_patterns.detect_all(full_text)` → regex matches (PAN, Aadhaar, phone, email, account number, etc.)
   - `pii_context.extract_contextual_entities(...)` → label-value spatial extraction (e.g., "Name: Ravi Kumar")
   - Groups by normalised value, picks best evidence per group

5. **AI Vision resolution** (`ai_reasoning.analyze_entity_candidates`): Sends image + candidate list to the vision AI. Returns `entity_classifications` per value with `final_type` and confidence.

6. **Entity resolution** (`entity_resolution.resolve_entities`): Fuses scores using weights: AI 45%, deterministic 25%, OCR 15%, layout 15%. Applies confidence thresholds (≥0.50 deterministic-only, ≥0.35 with AI agreement).

7. **DPDP Rules Engine** (`dpdp_rules_engine.evaluate_dpdp_compliance`):
   - Classifies screen types (SCR-01 to SCR-13)
   - Builds PII inventory map (PRESENT/ABSENT for ~60 PII IDs)
   - Evaluates applicable rules based on screen type
   - Returns verdict: `YES` / `NO` / `INCONCLUSIVE`

8. **AI Text Audit** (`services/ai_service.run_text_analysis`): Calls SambaNova with YAML-compacted OCR+entity payload. Returns structured JSON with `violations_found`, `violation_details`, `recommendations`, etc.

---

## 6. DPDP Rules Engine Architecture

Source: `backend/dpdp_rules_engine.py` and `rules_engine/DPDP_Rules_Engine.md`.

### Screen Types (PART B)
13 screen types, classified by keyword matching from OCR text:

| ID | Name |
|----|------|
| SCR-01 | KYC / Onboarding |
| SCR-02 | Account Summary / Dashboard |
| SCR-03 | Transaction History |
| SCR-04 | Debit/Credit Card Info |
| SCR-05 | Fund Transfer / Payment |
| SCR-06 | Mobile Recharge |
| SCR-07 | Profile / Settings |
| SCR-08 | Loan / Credit Application |
| SCR-09 | Video KYC |
| SCR-10 | Notification / Consent Banner |
| SCR-11 | Third-Party Offer / Ad |
| SCR-12 | Error / Debug Screen |
| SCR-13 | Login / Auth |

Multiple screen types can match a single image. Primary = highest keyword-hit count.

### PII Registry (PART A) — `dpdp_pii_registry.py`
~60 PII parameter IDs grouped as:
- `KYC-01..05`: PAN, Aadhaar, Passport, Voter ID, Driving Licence
- `ID-01..20`: Full Name, Customer ID, DOB, Gender, Address, Religion, Caste, etc.
- `FIN-01..11`: Bank Account, Cards, Credit Score, Balance, UPI, Income, Tax
- `BIO-01..02`: Fingerprints, Voice
- `ONL-01..04`: Username, Password, IP, Cookie
- `CHD-01..05`: Children's data
- `OTH-01..03`: Call/Video recordings, CCTV

### Rule Applicability Matrix (PART D)
Each rule maps to a set of screen types. A rule is only evaluated if the current screen matches. 26 rules total:

| Prefix | Coverage |
|--------|---------|
| `RULE-DM-*` | Data Minimisation (6 rules) |
| `RULE-CN-*` | Consent & Notice (6 rules) |
| `RULE-SEC-*` | Security (5 rules) |
| `RULE-RET-*` | Retention (2 rules) |
| `RULE-CHD-*` | Children (3 rules) |
| `RULE-TP-*` | Third-Party (2 rules) |
| `RULE-SEN-*` | Sensitive Data (3 rules) |
| `RULE-GR-01` | Grievance Redressal |
| `RULE-ACC-01` | Data Accuracy |

Each rule function takes `(pii_inventory, entities, full_text)` and returns either a violation dict or `None`.

### Verdict Logic (PART G)
```
violations found → "YES"
inconclusive conditions AND no violations → "INCONCLUSIVE"
otherwise → "NO"
```
Inconclusive triggers: low OCR confidence (<0.4), low screen classification confidence, partial card masking.

---

## 7. AI Provider Architecture

### Vision AI — `backend/ai_providers.py`
Abstract class `VisionAIProvider` with method `analyze(image_bytes, mime_type, prompt)`. One concrete class: `GenericVisionProvider` (OpenAI-compatible). Configured via env vars:
- `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`, `AI_TIMEOUT_SECONDS`

**To swap the vision AI:** subclass `VisionAIProvider`, override `analyze()`, then return it from `get_vision_provider()`.

### Text AI — `backend/services/ai_service.py`
Uses SambaNova's OpenAI-compatible `/v1/chat/completions`. Entry point: `run_text_analysis(document_type, ocr, entities, compliance, metadata)`. Builds YAML payload, posts to SambaNova, parses JSON response. Falls back deterministically if inference fails. Config: `SAMBANOVA_*` env vars.

**`HF_TEXT_MODEL`** is an alias for `SAMBANOVA_MODEL` — kept for backward-compatibility with `main.py` import.

---

## 8. Frontend Architecture

### Routing (`App.jsx`)
```
/                    → LoginPage
/upload              → UploadPage
/apk/status/:jobId   → ApkStatusPage
/select              → SelectionPage
/dpdp/process        → ProcessPage
/dpdp/pii            → PiiSelectionPage
/dpdp/result         → DpdpResultPage
/dpdp/ropa           → RopaPreviewPage
```
The entire `<BrowserRouter>` is wrapped in `<DpdpProvider>`, so all pages—including `/upload` and `/select`—share the global state.

### Global State — `useDpdpStore.jsx`
A `useReducer`-based context. Shape:
```js
{
  isProcess: null,          // true | false
  processType: '',          // string
  selectedPiis: [],         // string[] — PII types user selected
  customPiis: [],           // string[] — user-added custom types
  imageIds: [],             // number[] — DB IDs of uploaded images
  devMode: false,           // boolean — developer mode toggle (persisted in localStorage)
  selectedBaseline: null,   // { id, file_name } — baseline selected for comparison
}
```
Actions: `SET_IS_PROCESS`, `SET_PROCESS_TYPE`, `SET_IMAGE_IDS`, `TOGGLE_PII`, `ADD_CUSTOM_PII`, `REMOVE_CUSTOM_PII`, `SELECT_MANY`, `DESELECT_MANY`, `CLEAR_ALL`, `SET_DEV_MODE`, `SELECTED_BASELINE`, `RESET`.

`devMode` is initialised from `localStorage('devMode')` at module load time. `RESET` preserves both `devMode` and `selectedBaseline` so they survive navigation between scan sessions.

### Developer Mode — `DevModeToggle.jsx`
A button rendered on every page header (LoginPage, UploadPage, SelectionPage, PageShell). Accepts an optional `dispatch` prop to sync with the store. When `dispatch` is provided, it dispatches `SET_DEV_MODE`; it always writes to localStorage. On the UploadPage and PageShell, `dispatch` IS wired up so the store stays in sync.

### DpdpResultPage.jsx (largest component, ~1136 lines)
The main results dashboard. Key internals:
- **`computeConfidence`**: weighted score — OCR conf (40%), entity conf (30%), AI conf (20%), rule coverage (10%)
- **`DpdpVerdictPanel`**: Shows deterministic rules verdict + merged AI violations
- **`AiAnalysisPanel`**: Shows AI findings, recommendations, purpose limitation
- **`OcrBlockView`**: Block view / full-text toggle with PII highlighting
- **Tab system**: `verdict` | `ai` | `pii` | `ocr` | `devtools` (last tab only when devMode is true)
- **Multi-image**: `activeImage` index, one scan result per image
- Sidebar (`.ocr-results-sidebar`): scan metadata, screen type, action buttons

#### Dev Tools Tab
Visible only when `devMode` is true in the store. Contains:
1. **Correction Verification** — shown when `selectedBaseline` is set. After scans complete, fetches the baseline's full payload via `GET /api/dev/baseline/{id}`, iterates `corrections_expected` rule IDs, compares each against the new scan's `violation_details`, and renders a table with ✅ Corrected / ❌ Still present badges.
2. **Mark Violations to Correct** — checklist of all current violations (deduplicated by rule_id), toggled into `checkedRules` state.
3. **Save Baseline** — name input + button that POSTs `{file_name, payload: {images, corrections_expected}}` to `/api/dev/baseline`.

### UploadPage.jsx — Baseline Comparison (dev mode)
When `devMode` is true, renders a "Compare against baseline" section below the upload card:
- **On mount**: fetches `GET /api/dev/baseline` to list the user's saved baselines.
- **Radio list**: click to select a baseline (stored via `SELECTED_BASELINE` dispatch).
- **Delete button**: per-item, opens a confirmation dialog, calls `DELETE /api/dev/baseline/{id}`.
- **Selected indicator**: green banner showing the active baseline name.
- The `selectedBaseline` persists in the store, carried through the scan flow to `DpdpResultPage`.

The component calls `GET http://localhost:5000/api/pii/{id}` for each image ID stored in `state.imageIds`. Token is read from `localStorage.getItem('token')`.

### RopaPreviewPage.jsx
- Receives `location.state.scanResults` (passed via `navigate`)
- On mount, POSTs to `/api/ropa/generate`
- Displays 31-field ROPA form, organised into 7 section tabs
- Each field is editable via `FieldCard` component; edit changes local `ropaData` state
- Export calls `/api/ropa/export` → tries `window.showSaveFilePicker` first, falls back to anchor download
- "Back" button navigates to `/dpdp/result` passing `scanResults` as `location.state` so the result page skips re-scanning

---

## 9. Data Shape Reference

### `/api/pii/{id}` response
```json
{
  "image_id": 1,
  "filename": "screenshot.jpg",
  "ocr": {
    "total_blocks": 45,
    "avg_confidence": 0.87,
    "blocks": [{"text": "...", "confidence": 0.92, "bbox": [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]}],
    "full_text": "...",
    "lines": [...],
    "rows": [...],
    "columns": [...]
  },
  "entities": [
    {
      "type": "Bank Account Number",
      "raw_type": "BANK_ACCOUNT",
      "value": "XXXX1234",
      "category": "Financial Data",
      "confidence": 0.87,
      "masked": false,
      "risk": "Critical",
      "bbox": [...],
      "ocr_block_indices": [3],
      "reason": "...",
      "source_rule": "HybridAIResolution"
    }
  ],
  "compliance": {
    "total_entities": 5,
    "by_risk": {"Critical": 1, "High": 2, "Medium": 1, "Low": 1}
  },
  "dpdp_verdict": {
    "screen_type": "SCR-03 (Transaction History)",
    "screen_types": ["SCR-03"],
    "screen_classification": {...},
    "pii_inventory": {"FIN-01": "PRESENT", "KYC-02": "ABSENT", ...},
    "rules_evaluated": ["RULE-SEC-02", "RULE-RET-01", ...],
    "violations_found": "YES",
    "violation_details": [
      {
        "rule_id": "RULE-SEC-02",
        "pii_involved": ["FIN-01"],
        "act_section": "Section 8(5)",
        "section_title": "Security safeguards",
        "finding": "Full account number unmasked in transaction history.",
        "severity": "HIGH",
        "penalty_reference": "Up to ₹250 crore"
      }
    ],
    "overall_severity": "HIGH",
    "notes": [],
    "total_entities": 5,
    "by_risk": {...}
  },
  "ai_analysis": {
    "enabled": true,
    "provider": "sambanova",
    "status": "success",
    "violations_found": "YES",
    "overall_risk": "HIGH",
    "screen_sensitivity": "HIGH",
    "ai_summary": "...",
    "purpose_limitation": {"assessment": "...", "excessive_data_exposure": true},
    "violation_details": [...],
    "findings": [...],
    "recommendations": [...],
    "limitations": [...]
  },
  "candidate_entities": [...],
  "semantic_resolution": {...}
}
```

### Entity `raw_type` values (from `entity_catalog.py` / `ENTITY_TO_PII_IDS`)
`PAN`, `AADHAAR_UNMASKED`, `AADHAAR_MASKED`, `BANK_ACCOUNT`, `CREDIT_DEBIT_CARD`, `MASKED_CARD`, `EMAIL`, `PHONE_IN`, `UPI_HANDLE`, `ACCOUNT_BALANCE`, `ACCOUNT_HOLDER_NAME`, `CUSTOMER_ID`, `DATE_OF_BIRTH`, `IFSC`, `TRANSACTION_REFERENCE`, `TRANSACTION_AMOUNT`, `TRANSACTION_HISTORY`, `_KW_PASSWORD`

### Entity risk levels
`"Critical"` — Aadhaar unmasked, full card, password  
`"High"` — PAN, bank account, balance, email  
`"Medium"` — Phone, customer ID  
`"Low"` — transaction references, IFSC

---

## 10. Database Schema

Three tables, created on startup via `lifespan()`:

```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(100) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE images (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(100) NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  image_data TEXT NOT NULL,       -- base64 data URI
  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dev_baselines (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(100) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  payload JSONB NOT NULL,          -- { images: [...], corrections_expected: [rule_id, ...] }
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Important:** Images are stored as base64 data URIs in the DB and **deleted after `/api/pii` scan completes** (lines 558–566 in `main.py`). There is also a background cleanup task that deletes images older than 15 minutes every 5 minutes.

**`dev_baselines`** stores developer regression-testing snapshots. The `payload` JSONB contains the full scan results for every image plus a `corrections_expected` array of rule IDs that should be fixed in the next scan. Baselines are never auto-deleted.

> ⚠️ **Critical lifecycle rule:** Once `/api/pii/{id}` returns, that image ID is permanently gone from the DB. Any frontend navigation that carries old image IDs forward (e.g. via `location.state` or a merged array) will receive a 404 on the next scan. Always derive image IDs from a fresh DB fetch, not from cached router state.

---

## 11. CSS / Styling Conventions

- **`index.css`**: global design tokens, dark mode variables, shared utility classes
- **`dpdp.css`**: all result page classes (`.ocr-results-layout`, `.pii-entity-row`, `.ai-analysis-wrap`, `.dpdp-violation-card`, etc.)
- **`ropa.css`**: ROPA page classes
- **`login.css`**: login page
- No TailwindCSS — pure Vanilla CSS with CSS custom properties
- Dark mode is toggled by adding `class="dark"` to `<html>` via `DarkModeToggle.jsx`

---

## 12. Known Patterns & Gotchas

1. **OCR threading:** EasyOCR is a lazy singleton protected by `threading.Lock`. All OCR calls go through `loop.run_in_executor(None, _run_ocr_sync, image_bytes)` to avoid blocking the async event loop.

2. **Hindi numeral transliteration:** `str.maketrans('०१२३४५६७८९', '0123456789')` is applied to all OCR output. The Rupee symbol is restored by regex substituting OCR artifacts (`=`, `..=`) before currency amounts.

3. **Aadhaar false positives:** 12-digit numbers in transaction contexts are suppressed — `aadhaar_validator.py` runs Verhoeff checksum AND checks for banking transaction keywords. Confidence is capped at 0.18 if transaction context present without checksum support.

4. **Screen multi-classification:** A screenshot can match multiple screen types. ALL applicable rules for ALL matched types are evaluated. The `rules_evaluated` list can be long.

5. **AI Vision vs AI Text:** Two separate AI calls in `/api/pii`:
   - **Vision AI** (`ai_providers.py`): multimodal, sees the image + candidates, classifies entity types
   - **Text AI** (`services/ai_service.py`): text-only, SambaNova, audits compliance findings

6. **ROPA back-navigation:** When navigating back from `/dpdp/ropa` to `/dpdp/result`, scan results are passed via `location.state.scanResults`. The result page checks `preloaded.length` and skips re-scanning if data is present.

7. **CORS:** Backend allows all origins (`allow_origins=["*"]`). Fine for dev, should be restricted in production.

8. **`pii_rules.py` is deprecated:** The old `generate_compliance_report()` is still imported in `main.py` but the real compliance work now lives in `dpdp_rules_engine.py`.

9. **Frontend API base URL is hardcoded:** All fetches use `http://localhost:5000`. For deployment, this needs to be an env var or Vite proxy config.

10. **SSL bypass in `ai_service.py`:** `ctx.verify_mode = ssl.CERT_NONE` — this bypasses TLS cert verification. Workaround for Windows Python CA cert issues.

11. **Image IDs are single-use — never carry them across scans.** The backend deletes each image row after `/api/pii` completes. If any image ID from a previous session leaks into a new scan's request (via stale `location.state`, merged arrays, or a non-reset store), the backend returns HTTP 404 for that ID. The frontend defends against this in three places:
    - **`UploadPage.jsx` `handleContinue`**: navigates to `/select` with only the freshly uploaded IDs (`data.image_ids`), never merging with `location.state.imageIds`.
    - **`SelectionPage.jsx`**: computes `liveImageIds = images.map(img => img.id)` from the actual DB-fetched image list and passes those (not `location.state.imageIds`) to `/dpdp/process`.
    - **`ProcessPage.jsx` `useEffect`**: always dispatches `RESET` before `SET_IMAGE_IDS` so that any stale store state from a previous scan session is cleared.

---

## 13. Adding New Features — Common Patterns

### Add a new DPDP rule
1. Add the rule ID → screen type set mapping in `RULE_APPLICABILITY` dict in `dpdp_rules_engine.py`
2. Write a `_ruleXX(pii_inv, entities, full_text)` function returning `_v(...)` or `None`
3. Register it in `_RULE_CHECKERS` dict
4. No frontend changes needed — violation cards render dynamically

### Add a new PII entity type
1. Add entry to `PII_REGISTRY` in `dpdp_pii_registry.py`
2. Add mapping in `ENTITY_TO_PII_IDS` (entity raw_type → PII ID list)
3. Add regex in `pii_patterns.py` or context extraction in `pii_context.py`
4. Add `DISPLAY_NAME`, `CATEGORY_MAP`, `RISK_MAP` entries in `entity_catalog.py`

### Add a new screen type
1. Add `SCR-XX` → label in `SCREEN_TYPES` dict in `dpdp_screen_classifier.py`
2. Add keyword signals tuple in `_SCREEN_SIGNALS`
3. Add legacy doc type mapping in `_SCR_TO_LEGACY`
4. Add new rules applicable to the screen in `RULE_APPLICABILITY` in `dpdp_rules_engine.py`

### Add a new frontend tab to the result page
`DpdpResultPage.jsx` — find the tab definition array:
```jsx
[
  { key: 'verdict',  label: '...' },
  { key: 'ai',      label: '...' },
  { key: 'pii',     label: '...' },
  { key: 'ocr',     label: '...' },
  // Dev Tools tab added conditionally when devMode is true:
  ...(devMode ? [{ key: 'devtools', label: '🛠 Dev Tools' }] : []),
]
```
Add a new entry, then add a conditional render block: `{activeTab === 'newkey' && <YourPanel />}`.

### Add a new ROPA field
1. Add field key → section mapping in `FIELD_SECTION_MAP` in `RopaPreviewPage.jsx`
2. Add label in `FIELD_LABELS`
3. Add population logic in `ropa_generator.py` (`generate_ropa_entry` function)

### Swap the vision AI provider
1. Create a new class extending `VisionAIProvider` in `ai_providers.py`
2. Override `configured` property and `analyze()` method
3. Return your class from `get_vision_provider()`

### Swap the text AI provider
1. Edit `services/ai_service.py`
2. Replace `_call_sambanova()` with your provider's API call
3. Update env var names and config section at top of file

---

## 14. DPDP Act Quick Reference

Key sections the rules engine enforces:

| Section | Title | Penalty |
|---------|-------|---------|
| Section 4 | Grounds for processing | Up to ₹50 crore |
| Section 5(1) | Notice | Up to ₹50 crore |
| Section 6(1) | Consent / Data Minimisation | Up to ₹50 crore |
| Section 8(3) | Data accuracy | Up to ₹50 crore |
| Section 8(5) | Security safeguards | Up to ₹250 crore |
| Section 8(7) | Retention & erasure | Up to ₹50 crore |
| Section 8(10) | Grievance redressal | Up to ₹50 crore |
| Section 9(1) | Children — parental consent | Up to ₹200 crore |
| Section 9(3) | Children — no tracking/targeting | Up to ₹200 crore |

Full section reference is in `backend/dpdp_act_sections.md`.

---

## 15. File Size / Complexity Guide

For orientation when making changes:

| File | Lines | Complexity | Notes |
|------|-------|-----------|-------|
| `DpdpResultPage.jsx` | 1136 | High | Multiple sub-components, 5 tabs, baseline comparison, confidence computation |
| `main.py` | 1007 | High | All routes (incl. 4 baseline endpoints), DB lifecycle, OCR singleton |
| `dpdp.css` | 2366 | Medium | Result page + devtools + baseline comparison + dark mode styles |
| `services/ai_service.py` | 537 | Medium | SambaNova call, prompt, response normalisation |
| `layout_mapping.py` | ~600 | High | Spatial label-value association logic |
| `ai_reasoning.py` | ~600 | High | Vision AI prompt construction |
| `RopaPreviewPage.jsx` | 479 | Medium | 31-field form, section tabs, export |
| `dpdp_rules_engine.py` | 452 | Medium | 26 rule functions |
| `pii_classifier.py` | ~500 | Medium | PII classification heuristics |
| `ropa_generator.py` | ~530 | Medium | ROPA mapping from scan results |
| `UploadPage.jsx` | 436 | Medium | Image upload + baseline comparison section (dev mode) |
| `entity_resolution.py` | 230 | Medium | Confidence fusion logic |
| `candidate_generator.py` | 230 | Medium | Evidence aggregation |
| `ApkStatusPage.jsx` | 252 | Low | APK scan job status display |
| `dpdp_pii_registry.py` | 155 | Low | Static registry + inventory scan |
| `dpdp_screen_classifier.py` | 140 | Low | Keyword-based screen classification |
| `useDpdpStore.jsx` | 83 | Low | State reducer + devMode + selectedBaseline |
| `DevModeToggle.jsx` | 69 | Low | Dev mode toggle button with store dispatch |
