# PROJECT_BRIEF.md
> Feed this file at the start of each AI session to restore context without re-reading the codebase.

## Project
**DPDP Compliance Scanner & Accessibility Auditor** — An internal web tool for South Indian Bank (SIB) staff to scan document screenshots/images for DPDP (Digital Personal Data Protection) compliance by detecting PII entities, validating masking, and generating AI-assisted privacy/compliance reasoning. The DPDP Scanner is the primary active module; the Accessibility Auditor is owned by a separate team and must not be modified.

## Tech Stack
- **Language**: Python 3.11 (backend), JavaScript/JSX (frontend)
- **Framework**: FastAPI (backend API), React 19 + Vite (frontend SPA)
- **Key Libraries**:
  - Backend: `easyocr==1.7.2` (OCR engine, CPU-only), `asyncpg` (async PostgreSQL), `python-jose` (JWT auth), `passlib[bcrypt]` (password hashing), `python-dotenv`, `Pillow`, `numpy<2.0.0`, `opencv-python-headless`
  - Frontend: `react-router-dom`, vanilla CSS (no Tailwind — brand-compliant custom CSS in `dpdp.css`)
- **Infra**: Docker Compose (`frontend`, `backend`, `db`); PostgreSQL 15; images stored as Base64 data-URIs in the DB
- **AI Provider**: SambaNova Cloud using text-based reasoning models, configured through `SAMBANOVA_API_KEY` and `SAMBANOVA_MODEL=DeepSeek-V3.1`.

## Folder Structure
```text
backend/
  main.py                # FastAPI app, auth, upload/image APIs, OCR, PII scan orchestration
  document_classifier.py # Document type heuristics
  pii_patterns.py        # Regex catalogue + RawMatch model
  pii_context.py         # Context-aware entity extraction
  pii_classifier.py      # OCR-aware entity classification and priority rules
  pii_rules.py           # DEPRECATED — old masking-only compliance scoring
  dpdp_pii_registry.py   # PART A: PII parameter registry + PRESENT/ABSENT mapping
  dpdp_screen_classifier.py # PART B: 13 screen type classifier (SCR-01..SCR-13)
  dpdp_rules_engine.py   # PART C-G: 26-rule evaluator; section-based violations, no score/grade
  dpdp_act_sections.md   # Complete DPDP Act 2023 section reference (Sections 1–44 + Schedule)
  ocr_structure.py       # OCR line/row reconstruction and context preservation
  banking_context.py     # Transaction-first banking row parser
  aadhaar_validator.py   # Aadhaar validation + Verhoeff checksum logic
  ai_providers.py        # Swappable multimodal provider adapters
  ai_reasoning.py        # AI reasoning layer and normalized AI output
  prompt_formatter.py    # YAML-oriented prompt payload formatter
  risk_scoring.py        # Combined rule + AI risk scoring (no longer depends on rule engine score)
  services/
    ai_service.py        # LLM prompt builder; system prompt includes full DPDP Act section list
  tests/
    test_pii_classifier.py # Regression coverage for transaction-vs-Aadhaar behavior
  requirements.txt
  Dockerfile

dpdp-app/
  src/
    LoginPage.jsx
    UploadPage.jsx
    SelectionPage.jsx
    dpdp/
      ProcessPage.jsx
      PiiSelectionPage.jsx
      DpdpResultPage.jsx   # Rule-based + AI compliance dashboard
      PageShell.jsx
      useDpdpStore.jsx
      dpdp.css

docker-compose.yml       # Backend :5000, frontend :5173, PostgreSQL :5432
project_brief/           # This file
brand-guidelines/        # SIB brand skill/reference
frontend-design/         # Frontend design skill/reference
```

## Key Conventions
- **Do NOT modify** anything in the Accessibility Auditor module — it belongs to another team.
- **All API calls** use `http://localhost:5000/api/...` from frontend components. Vite proxy also maps `/api -> http://backend:5000` for in-Docker requests.
- **Auth**: JWT stored in `localStorage` as `token`. Every protected endpoint reads `Authorization: Bearer <token>` via `Depends(get_current_user)`.
- **Images**: Stored as `data:<mime>;base64,<data>` strings in `images.image_data` (PostgreSQL `TEXT`). Stored only temporarily; the scan endpoint deletes transient images after analysis.
- **Database name in Docker**: `dpdp_scanner`
- **Styling**: Brand colours use global CSS classes in `App.css`. DPDP module styles live in `dpdp.css`. Preserve header/footer/navigation.
- **Frontend constraint**: Do not redesign unrelated pages. Only extend the DPDP results experience when needed.

## Pipeline Architecture
Current scan path:

`Upload -> DB image record -> EasyOCR -> OCR structure parser -> banking transaction context detection -> Aadhaar validation -> PII classification -> DPDP Rules Engine (26 rules, section-based violations) -> AI reasoning (section-aware, DPDP Act section violation detection) -> combined risk scoring -> frontend dashboard`

Important implementation details:
- EasyOCR remains the OCR engine. Do not swap OCR engines to fix classification issues.
- `ocr_structure.py` is the source of truth for reconstructed OCR `full_text` and `lines`.
- Transaction rows such as `UPI/SIBL/649844712639/...` must remain transaction-shaped during OCR post-processing.
- Aadhaar classification requires stronger validation than a raw 12-digit regex:
  - normalized 12-digit format
  - valid leading digit heuristic
  - valid Verhoeff checksum
  - positive Aadhaar context
  - non-transaction banking context
- Transaction references override overlapping Aadhaar/account interpretations in statement-like rows.

## API Surface
- `POST /api/login`
- `POST /api/upload`
- `GET /api/images`
- `DELETE /api/images/{image_id}`
- `POST /api/ocr/{image_id}`
- `POST /api/pii/{image_id}`
- `POST /api/ocr-debug`

`POST /api/pii/{image_id}` returns:
- `ocr`
  - `total_blocks`, `avg_confidence`, `blocks`, `full_text`, `lines`
- `entities`
  - includes `type`, `classification`, `raw_type`, `value`, `confidence`, `risk`, `reason`, `source_rule`, `document_type`
  - explainability fields include `ocr_line_indices`, `ocr_context`, `validation_status`, `aadhaar_checksum_valid`, `contextual_reasoning`
- `compliance`
  - `total_entities`, `by_risk` only — score/grade/flags removed
- `ai_analysis`
- `dpdp_verdict`
  - `screen_type`, `screen_types`, `screen_classification`
  - `pii_inventory`, `rules_evaluated`
  - `violations_found` (YES / NO / INCONCLUSIVE)
  - `violation_details[]` — each item has: `rule_id`, `act_section`, `section_title`, `pii_involved`, `finding`, `severity`, `penalty_reference`
  - `overall_severity`, `notes`, `total_entities`, `by_risk`

`ai_analysis` is expected on every successful scan response:
- `status` is `success` when the AI provider returns a valid answer
- `status` is `fallback` when AI fails and deterministic reasoning is shown instead

## Current State
- ✅ Auth flow with JWT login and seeded staff accounts (`sanoj/sib123`, `admin/admin`, etc.)
- ✅ Multi-image upload -> PostgreSQL Base64 storage -> thumbnail review page
- ✅ DPDP Scanner flow: Process ID -> PII Category Selection -> Upload -> Results
- ✅ EasyOCR pipeline with lazy singleton initialization and structured OCR parsing
- ✅ OCR line preservation via `ocr_structure.py`, including `ocr.lines` in API responses
- ✅ Banking-aware PII classifier:
  - transaction reference detection from UPI/IMPS/NEFT/RTGS/ref/UTR patterns
  - Aadhaar Verhoeff checksum validation
  - transaction-first suppression rules for false Aadhaar detections
  - account-number context checks
- ✅ Regression tests for mini-statement transaction IDs vs Aadhaar false positives
- ✅ Compliance scoring **removed**: score (0–100), grade (A–F), flags list, and `ScoreRing` UI component all deleted
- ✅ DPDP Act 2023 section reference (`backend/dpdp_act_sections.md`):
  - All sections extracted (Sections 1–44, Schedule with penalty amounts)
  - Used as the AI system prompt reference for section-level violation detection
- ✅ DPDP Rules Engine v2.0:
  - 26 rules across 9 groups: data minimisation, consent & notice, data security, retention, children's data, third-party sharing, sensitive data, grievance redressal, data accuracy
  - **Section-based violation reporting**: each violation maps to a specific DPDP Act 2023 section (e.g., `Section 6(1)`, `Section 8(5)`)
  - Each violation carries: `act_section`, `section_title`, `severity`, `penalty_reference`
  - `SECTION_TITLES` and `PENALTY_REFERENCE` lookup dicts built into the engine
  - INCONCLUSIVE verdict support per PART F conditions
- ✅ AI service system prompt (`services/ai_service.py`) rewritten with all 30+ DPDP Act sections; AI now returns `act_section`, `section_title`, `penalty_reference` per violation; `rule_id` and `screen_type` removed from AI output schema
- ✅ DPDP result dashboard — full UI overhaul (`DpdpResultPage.jsx`):
  - **Summary banner**: `VERDICT | CONFIDENCE LEVEL | VIOLATIONS | PII ENTITIES | SCREEN`
    - `CONFIDENCE LEVEL` = weighted combination of OCR conf (40%) + entity conf (30%) + AI conf (20%) + rule coverage (10%); shows `Pending` when unavailable, never a dash
    - `SCREEN` item removed
  - **Flags tab** removed (legacy `FlagsPanel` component deleted)
  - **ViolationCard** redesigned: shows `act_section` badge, `section_title`, severity, category, finding, PII tags, and penalty reference (`⚠ Penalty: Up to ₹250 crore`)
  - **Violation merge logic** updated: deduplicates by `act_section` instead of `rule_id`
  - **Sidebar — Rule Set Explorer** (replaces old Sections Violated card):
    - Shows all 13 SCR screen types from the rules engine
    - Active SCRs determined from `rules_evaluated` (not just `screen_types`)
    - Starts **expanded** by default
    - Each SCR card: `SCR-XX` badge, risk badge (or ✓ Compliant), name, tags, rule count (`triggered/applicable`), PII count
    - Expandable detail: purpose, Rules Triggered list with finding excerpts, Detected PII tags, Risk / Confidence / Matched Screens stats
    - Falls back to "No rule sets available" if verdict is null
- ✅ Background cleanup of abandoned images older than 15 minutes
- ✅ Scan endpoint deletes analyzed image records after processing to reduce sensitive data retention
- ✅ EasyOCR text normalization:
  - Transliterates Devanagari numerals back to ASCII numerals (०१२३४५६७८९ → 0123456789)
  - Contextual regex replacement recovers misclassified Indian Rupee symbols (₹) often misread as `3`, `=`, or `..=`
- ✅ AI Provider & Terminology Cleanup:
  - Consolidated Qwen and HuggingFace vision providers into a single `GenericVisionProvider` configurable via environment variables.
  - Standardized all UI messages, logs, and docstrings to use generic "AI model" and "OCR" terms instead of hardcoded model or engine names.

## Known Good Regression Case
The mini-statement screenshot used during recent debugging must classify these as `TRANSACTION_REFERENCE`, not Aadhaar:
- `649844712639`
- `649745822146`
- `612972952283`
- `612933455496`
- `612846027773`
- `649419976854`
- `612816647683`

The same screenshot should keep:
- `0587053000016422` as `BANK_ACCOUNT`

## Out of Scope
- Accessibility Auditor module — separate team, do not modify any related files
- Mobile app — web only
- GPU/CUDA acceleration — Docker environment is CPU-only
- Permanent storage of scan results or AI findings
- Replacing OCR engines to solve classification quality problems

## Active Work
- EasyOCR model weights still download on the first-ever scan request (~30s cold start), then remain cached in the container
- Export/report generation (PDF/JSON download) is still not implemented
- AI quality depends on valid SambaNova token access and runtime connectivity from the backend container
- Token usage increased by ~630 tokens/request due to expanded system prompt (DPDP Act sections); at DeepSeek-V3.1 pricing this is negligible (~$0.00017/scan)

## Design Decisions (Do Not Revert)
- **No compliance score or grade**: The 0–100 score and A–F grade system has been permanently removed. Do not re-add it. Violations are expressed at the Act-section level only.
- **No SCR-XX or RULE-XX display on result screen**: Rule IDs and screen classification codes are internal to the rules engine. They must not be displayed in the result UI.
- **Confidence Level replaces Score in the summary banner**: The confidence metric is a weighted signal (OCR + entity + AI + rule coverage), not a compliance verdict.
- **Rule Set Explorer is the canonical sidebar widget**: It replaces the old ScoreRing + Sections Violated card. It starts expanded. Do not collapse it by default or move it below the AI Posture card.
- **`dpdp_verdict` is the authoritative compliance output**: `compliance` dict only contains `total_entities` and `by_risk`. All violation details live in `dpdp_verdict.violation_details[]`.
