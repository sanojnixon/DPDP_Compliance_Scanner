# DPDP Compliance Scanner 

An automated, full-stack compliance auditor designed to scan and verify mobile banking applications for compliance with India's **Digital Personal Data Protection (DPDP) Act, 2023** and audit accessibility guidelines.

This system processes application screenshots to detect personally identifiable information (PII), assess data exposure against deterministic legal rules, run a dual-stage AI verification pass, and generate compliance reports alongside structured **ROPA (Record of Processing Activities)** documents.

---

## 🚀 Key Features

* **Advanced PII Detection Pipeline:** Uses a hybrid approach combining OCR (EasyOCR), regular expressions, spatial layout mapping, and multimodal Vision AI to identify sensitive entities (such as Aadhaar, PAN, Bank Accounts, Passwords, UPI IDs, and Customer Names) and evaluate their masking/exposure status.
* **DPDP Compliance Rules Engine:** Automatically maps screenshots to 13 distinct screen classifications (e.g., KYC onboarding, dashboards, transaction histories) and audits them against **26 legal rules** derived directly from the DPDP Act (Notice, Consent, Data Minimization, Security Safeguards, and Children's Data protection).
* **Dual-Stage AI Analysis:** 
  * **Vision AI:** Semantically resolves OCR candidates directly from the image layout to eliminate false positives.
  * **Text-Based LLM Audit (via SambaNova):** Provides contextual legal analysis, risk assessments, and actionable remediation steps.
* **Automated ROPA Generator:** Instantly translates compliance scan findings into a 31-field Record of Processing Activities (ROPA) form, ready to export as a formatted `.xlsx` spreadsheet matching standard Indian banking fiduciary templates.
* **Regression Testing & Baselines (Developer Mode):** Allows developers to save current scan profiles as "baselines" and compare future scans against them to verify if compliance violations (e.g., exposed credit cards or unmasked Aadhaar numbers) have been successfully corrected.

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| **Frontend** | React 19, Vite 8, React Router 7, Vanilla CSS (with Dark Mode support) |
| **Backend** | Python 3, FastAPI, asyncpg |
| **Database** | PostgreSQL 15 |
| **OCR Engine** | EasyOCR (English & Hindi) |
| **AI Processing** | OpenAI-compatible Vision API (for spatial classification) + SambaNova Cloud API (for legal audits) |
| **Orchestration** | Docker & Docker Compose |

---

## 🔄 How the Scan Pipeline Works

```
Screenshot Upload 
       │
       ▼
 [ 1. OCR Extraction ] ──► Standardizes Hindi/English text & numerals
       │
       ▼
 [ 2. Layout Mapping ] ──► Groups text into lines, rows, and spatial columns
       │
       ▼
 [ 3. Candidate Gen. ] ──► Regex & contextual pattern matchers locate PII
       │
       ▼
 [ 4. Vision AI Pass ] ──► Verifies layout context and resolves false positives
       │
       ▼
 [ 5. Rules Engine   ] ──► Checks screen-specific rules (e.g. Card Masking on SCR-04)
       │
       ▼
 [ 6. LLM Text Audit ] ──► Evaluates legal compliance & builds recommendations
       │
       ▼
[ Detailed Report & ROPA Output ]
```

---

## ⚙️ Quick Start

### Prerequisites
* Docker & Docker Compose installed.
* API credentials for your chosen LLM and Vision AI providers.

### Running with Docker Compose
1. Clone this repository:
   ```bash
   git clone https://github.com/sanojnixon/DPDP_Compliance_Scanner.git
   cd DPDP_Compliance_Scanner
   ```
2. Configure your API keys in the `backend/.env` file.
3. Start the entire system:
   ```bash
   docker-compose up --build
   ```
4. Access the applications:
   * **Frontend:** `http://localhost:5173`
   * **Backend API:** `http://localhost:5000`
