"""
ropa_generator.py — ROPA Field Mapping Engine
===============================================
Converts DPDP scan results (entities, verdict, AI analysis) into structured
ROPA entries matching the SIB Fiduciary_RoPA Excel template (31 columns).

Deterministic mappings are primary; AI-assisted inference is secondary.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Column definitions matching the Excel template ────────────────────────────
ROPA_COLUMNS = [
    # (key, excel_col, header, section, required)
    ("serial",              "A",  "#",                                          "General Information", False),
    ("department",          "B",  "Department",                                 "General Information", True),
    ("spoc_name",           "C",  "SPOC Name",                                 "General Information", False),
    ("application_name",    "D",  "Application/Platform Name",                 "General Information", True),
    ("process",             "E",  "Process",                                   "General Information", True),
    ("purpose",             "F",  "Purpose of processing",                     "General Information", True),
    ("description",         "G",  "Description of the data processing",        "Process Details", True),
    ("data_principal_cats", "H",  "Categories of Data principals involved",    "Process Details", True),
    ("includes_children",   "I",  "Data principals include person with disability/children's", "Process Details", True),
    ("child_tracking",      "J",  "Tracking/behavioural monitoring of children","Process Details", True),
    ("personal_data_cats",  "K",  "Categories of Personal Data processed",     "Process Details", True),
    ("data_source",         "L",  "Source of personal data",                   "Process Details", True),
    ("grounds",             "M",  "Grounds for processing",                    "Process Details", True),
    ("consent_type",        "N",  "Consent type (Physical, Digital)",          "Process Details", False),
    ("automated_decisions", "O",  "Automated decision making/profiling?",      "Automated Decision Making", False),
    ("data_principal_rights","P", "Rights of Data Principals",                 "Rights of Data Principals", False),
    ("processor_name",      "Q",  "Data processor(s)",                         "Processor Information", False),
    ("dpa_in_place",        "R",  "Data Processing Agreement in place?",       "Processor Information", False),
    ("third_party_safeguards","S","Security safeguards for third parties",     "Processor Information", False),
    ("other_recipients",    "T",  "Other recipients (Internal/External)",      "Other Recipients", False),
    ("transfer_outside",    "U",  "Data transferred outside India?",           "Data Transfer", False),
    ("transfer_country",    "V",  "Country of transfer",                       "Data Transfer", False),
    ("transfer_purpose",    "W",  "Purpose of transfer",                       "Data Transfer", False),
    ("transfer_safeguards", "X",  "Transfer security safeguards",              "Data Transfer", False),
    ("storage_format",      "Y",  "Data storage format",                       "Data Storage", False),
    ("storage_location",    "Z",  "Where is data stored?",                     "Data Storage", False),
    ("retention_period",    "AA", "Retention period",                          "Data Storage", False),
    ("retention_purpose",   "AB", "Purpose for retention",                     "Data Storage", False),
    ("dpia_applicable",     "AC", "Is DPIA applicable?",                       "DPIA", False),
    ("dpia_link",           "AD", "Link to DPIA record",                       "DPIA", False),
    ("privacy_notice",      "AE", "Covered under Privacy Notice?",             "Privacy Notice", False),
]

ROPA_KEY_TO_COL = {col[0]: col[1] for col in ROPA_COLUMNS}
ROPA_KEY_TO_HEADER = {col[0]: col[2] for col in ROPA_COLUMNS}
ROPA_KEY_TO_SECTION = {col[0]: col[3] for col in ROPA_COLUMNS}
ROPA_REQUIRED_KEYS = {col[0] for col in ROPA_COLUMNS if col[4]}

# Standard DPDPA rights text
_RIGHTS_TEXT = (
    "1. Right to access\n"
    "2. Right to correction and erasure\n"
    "3. Right to grievance redressal\n"
    "4. Right to nominate\n"
    "5. Right to withdraw consent"
)

# PII ID → Personal Data Category mapping
_PII_TO_CATEGORY = {
    "KYC-01": "KYC Documents (PAN)",
    "KYC-02": "KYC Documents (Aadhaar)",
    "KYC-03": "KYC Documents (Passport)",
    "KYC-04": "KYC Documents (Voter ID)",
    "KYC-05": "KYC Documents (Driving Licence)",
    "ID-01": "Identity Data (Name)",
    "ID-04": "Identity Data (Phone Number)",
    "ID-07": "Identity Data (Email)",
    "ID-13": "Identity Data (Customer ID)",
    "ID-14": "Identity Data (Identification Number)",
    "FIN-01": "Financial Data (Bank Account)",
    "FIN-02": "Financial Data (Card Details)",
    "FIN-03": "Financial Data (IFSC)",
    "FIN-04": "Financial Data (UPI Handle)",
    "FIN-05": "Financial Data (Account Balance)",
    "FIN-06": "Financial Data (Transaction History)",
    "FIN-07": "Financial Data (Transaction Amount)",
    "BIO-01": "Biometric Data (Fingerprints)",
    "BIO-02": "Biometric Data (Voice Patterns)",
    "ONL-01": "Online Identifiers (Username)",
    "ONL-02": "Online Identifiers (Password)",
    "ONL-03": "Online Identifiers (IP Address)",
    "ONL-04": "Online Identifiers (Cookie/Session)",
    "CHD-01": "Children Data (Child Name)",
    "CHD-02": "Children Data (Child DOB)",
}

# Screen type → department inference
_SCREEN_TO_DEPARTMENT = {
    "Card Management": "Card Operations",
    "Account Summary / Dashboard": "Core Banking",
    "Transaction History / Passbook": "Core Banking",
    "Recharge / Bill Payment": "Digital Banking",
    "Loan / EMI Screen": "Retail Lending",
    "KYC / Onboarding": "Operations",
    "Fund Transfer": "Digital Banking",
    "Profile / Settings": "Core Banking",
    "Login / Authentication": "IT Security",
}

# Screen type → data source inference
_SCREEN_TO_SOURCE = {
    "Card Management": "Internal Systems (Card Management System)",
    "Account Summary / Dashboard": "Internal Systems (Core Banking)",
    "Transaction History / Passbook": "Internal Systems (Core Banking)",
    "KYC / Onboarding": "From Data Principals, Third Party (KYC vendors)",
    "Fund Transfer": "From Data Principals",
    "Profile / Settings": "From Data Principals",
    "Login / Authentication": "From Data Principals",
}


def _extract_app_name(ocr_text: str) -> str:
    """Extract application/platform name from OCR text."""
    patterns = [
        r"south\s+indian\s+bank",
        r"sibernet",
        r"sib\s+mirror\+?",
        r"internet\s+banking",
        r"mobile\s+banking",
        r"net\s+banking",
    ]
    for pat in patterns:
        if re.search(pat, ocr_text, re.IGNORECASE):
            return "SIB Mirror+ (Mobile Banking)"
    return "South Indian Bank Digital Platform"


def _extract_data_principal_categories(screen_types: list, pii_inventory: dict) -> str:
    """Determine categories of data principals from screen classification."""
    categories = set()
    categories.add("Customer")
    if any(pid in pii_inventory and pii_inventory[pid] == "PRESENT"
           for pid in ["CHD-01", "CHD-02"]):
        categories.add("Minor/Child")
    return ", ".join(sorted(categories))


def _check_children_involvement(pii_inventory: dict) -> str:
    """Check if children or persons with disability are involved."""
    child_pii = ["CHD-01", "CHD-02", "CHD-03", "CHD-04"]
    if any(pii_inventory.get(pid) == "PRESENT" for pid in child_pii):
        return "Minors"
    return "Not Applicable"


def _check_child_tracking(violations: list) -> str:
    """Check if child tracking/behavioural monitoring was detected."""
    if any(v.get("rule_id") == "RULE-CHD-03" for v in violations):
        return "Yes"
    return "No"


def _aggregate_personal_data_categories(pii_inventory: dict) -> str:
    """Build comma-separated list of personal data categories from PII inventory."""
    present_categories = set()
    for pid, status in pii_inventory.items():
        if status == "PRESENT" and pid in _PII_TO_CATEGORY:
            cat = _PII_TO_CATEGORY[pid].split(" (")[0]
            present_categories.add(cat)
    if not present_categories:
        return "General Personal Data"
    return ", ".join(sorted(present_categories))


def _infer_grounds(ocr_text: str, violations: list) -> str:
    """Infer lawful grounds for processing from OCR text."""
    tl = ocr_text.lower()
    if any(w in tl for w in ["i agree", "consent", "i accept"]):
        return "Consent"
    if any(w in tl for w in ["kyc", "verification", "aadhaar", "pan"]):
        return "Processing to fulfilling any obligation under any law in force in India."
    return "Processing is necessary for provision of services"


def _infer_consent_type(ocr_text: str, grounds: str) -> str:
    """Infer consent type if grounds is consent."""
    if "Consent" in grounds:
        return "Digital"
    return ""


def _check_dpia(pii_inventory: dict) -> str:
    """Check if DPIA is applicable based on sensitive data presence."""
    sensitive = ["BIO-01", "BIO-02", "CHD-01", "CHD-02"]
    if any(pii_inventory.get(pid) == "PRESENT" for pid in sensitive):
        return "Yes"
    return "No"


def _default_safeguards() -> str:
    return (
        "1. Access control\n"
        "2. Encryption/Anonymisation/Pseudonymisation\n"
        "3. Logging\n"
        "4. Privacy Training and Awareness"
    )


def generate_ropa_entry(
    scan_results: List[Dict[str, Any]],
    process_context: Optional[Dict[str, Any]] = None,
    serial: int = 1,
) -> Dict[str, Any]:
    """
    Generate a single ROPA entry by merging all scan results from a session.

    Args:
        scan_results: List of scan result dicts from /api/pii endpoint.
        process_context: Optional dict with keys like processType, department.
        serial: Row serial number.

    Returns:
        Dict with ROPA field keys mapped to populated values + metadata.
    """
    process_context = process_context or {}

    # ── Merge scan data across all images ─────────────────────────────────
    all_entities = []
    merged_pii_inventory = {}
    all_violations = []
    all_ocr_text = []
    screen_type_label = ""
    screen_types_set = set()
    ai_summary = ""
    ai_purpose = ""
    ai_description = ""

    for scan in scan_results:
        all_entities.extend(scan.get("entities", []))
        all_ocr_text.append(scan.get("ocr", {}).get("full_text", ""))

        verdict = scan.get("dpdp_verdict") or {}
        pii_inv = verdict.get("pii_inventory", {})
        for pid, status in pii_inv.items():
            if status == "PRESENT":
                merged_pii_inventory[pid] = "PRESENT"
            elif pid not in merged_pii_inventory:
                merged_pii_inventory[pid] = status

        all_violations.extend(verdict.get("violation_details", []))
        if verdict.get("screen_type"):
            screen_type_label = verdict["screen_type"]
        screen_types_set.update(verdict.get("screen_types", []))

        ai = scan.get("ai_analysis", {})
        if ai.get("ai_summary"):
            ai_summary = ai["ai_summary"]
        purpose_lim = ai.get("purpose_limitation", {})
        if purpose_lim.get("assessment"):
            ai_purpose = purpose_lim["assessment"]

    combined_text = "\n".join(all_ocr_text)

    # ── Deterministic field population ────────────────────────────────────
    app_name = _extract_app_name(combined_text)
    data_principals = _extract_data_principal_categories(list(screen_types_set), merged_pii_inventory)
    children_involved = _check_children_involvement(merged_pii_inventory)
    child_tracking = _check_child_tracking(all_violations)
    personal_data_cats = _aggregate_personal_data_categories(merged_pii_inventory)
    grounds = _infer_grounds(combined_text, all_violations)
    consent_type = _infer_consent_type(combined_text, grounds)
    dpia = _check_dpia(merged_pii_inventory)

    # ── AI-assisted fields ────────────────────────────────────────────────
    department = process_context.get("department", "")
    if not department and screen_type_label:
        base = screen_type_label.split("(")[0].strip()
        department = _SCREEN_TO_DEPARTMENT.get(base, "")

    process_name = process_context.get("processType", "")
    if not process_name and screen_type_label:
        process_name = screen_type_label.split("(")[0].strip()

    purpose = ai_purpose or process_context.get("purpose", "")
    if not purpose:
        purpose = f"Processing personal data for {process_name or 'banking services'}"

    description = ""
    if ai_summary:
        description = ai_summary[:500]
    elif process_name:
        description = (
            f"The {process_name} process within {app_name} handles personal data "
            f"including {personal_data_cats}. Data is collected digitally through "
            f"the mobile banking application."
        )

    data_source = ""
    if screen_type_label:
        base = screen_type_label.split("(")[0].strip()
        data_source = _SCREEN_TO_SOURCE.get(base, "From Data Principals")
    else:
        data_source = "From Data Principals"

    # ── Build entry ───────────────────────────────────────────────────────
    entry = {
        "serial":               serial,
        "department":           department,
        "spoc_name":            "",
        "application_name":     app_name,
        "process":              process_name,
        "purpose":              purpose,
        "description":          description,
        "data_principal_cats":  data_principals,
        "includes_children":    children_involved,
        "child_tracking":       child_tracking,
        "personal_data_cats":   personal_data_cats,
        "data_source":          data_source,
        "grounds":              grounds,
        "consent_type":         consent_type,
        "automated_decisions":  "No",
        "data_principal_rights": _RIGHTS_TEXT,
        "processor_name":       "",
        "dpa_in_place":         "",
        "third_party_safeguards": _default_safeguards(),
        "other_recipients":     "",
        "transfer_outside":     "No",
        "transfer_country":     "",
        "transfer_purpose":     "",
        "transfer_safeguards":  "",
        "storage_format":       "Digital",
        "storage_location":     "",
        "retention_period":     "",
        "retention_purpose":    "",
        "dpia_applicable":      dpia,
        "dpia_link":            "",
        "privacy_notice":       "",
    }

    # ── Source tracking (for UI badges) ───────────────────────────────────
    source_map = {}
    for key in entry:
        if key in ("serial",):
            source_map[key] = "system"
        elif key in ("application_name", "data_principal_cats", "includes_children",
                      "child_tracking", "personal_data_cats", "consent_type",
                      "storage_format", "data_principal_rights",
                      "third_party_safeguards", "transfer_outside"):
            source_map[key] = "scan" if entry[key] else "manual"
        elif key in ("department", "process", "purpose", "description",
                      "data_source", "grounds", "automated_decisions",
                      "dpia_applicable"):
            source_map[key] = "ai" if entry[key] else "manual"
        else:
            source_map[key] = "manual"

    # ── Validation ────────────────────────────────────────────────────────
    validation = _validate_entry(entry)

    logger.info(
        "[ROPA] Generated entry: serial=%d fields_filled=%d/%d warnings=%d",
        serial,
        sum(1 for v in entry.values() if v),
        len(entry),
        len(validation.get("warnings", [])),
    )

    return {
        "ropa_entry": entry,
        "source_map": source_map,
        "validation": validation,
        "pii_inventory": merged_pii_inventory,
        "screen_type": screen_type_label,
    }


def _validate_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a ROPA entry and return warnings/errors."""
    warnings = []
    errors = []

    for key in ROPA_REQUIRED_KEYS:
        if not entry.get(key):
            warnings.append({
                "field": key,
                "header": ROPA_KEY_TO_HEADER.get(key, key),
                "section": ROPA_KEY_TO_SECTION.get(key, ""),
                "message": f"{ROPA_KEY_TO_HEADER.get(key, key)} is required but empty.",
                "severity": "warning",
            })

    # Cross-field checks
    if entry.get("grounds") == "Consent" and not entry.get("consent_type"):
        warnings.append({
            "field": "consent_type",
            "header": "Consent type",
            "section": "Process Details",
            "message": "Consent ground selected but consent type not specified.",
            "severity": "warning",
        })

    if entry.get("transfer_outside") == "Yes":
        for dep_key in ("transfer_country", "transfer_purpose", "transfer_safeguards"):
            if not entry.get(dep_key):
                warnings.append({
                    "field": dep_key,
                    "header": ROPA_KEY_TO_HEADER.get(dep_key, dep_key),
                    "section": "Data Transfer",
                    "message": f"Data transfer is 'Yes' but {ROPA_KEY_TO_HEADER.get(dep_key, dep_key)} is empty.",
                    "severity": "warning",
                })

    if entry.get("includes_children") != "Not Applicable" and entry.get("child_tracking") == "":
        warnings.append({
            "field": "child_tracking",
            "header": "Child tracking",
            "section": "Process Details",
            "message": "Children are involved but child tracking field is empty.",
            "severity": "warning",
        })

    filled = sum(1 for v in entry.values() if v)
    total = len(entry)
    completion = round(filled / total * 100) if total else 0

    return {
        "warnings": warnings,
        "errors": errors,
        "completion_pct": completion,
        "filled_count": filled,
        "total_count": total,
    }


def generate_personal_data_inventory(pii_inventory: Dict[str, str]) -> Dict[str, Any]:
    """
    Generate the Personal Data Inventory sheet data from PII scan results.
    Maps detected PII IDs to the template's category/parameter structure.
    """
    inventory = {}

    pii_to_inv = {
        "KYC-01": ("KYC Documents", "PAN Details"),
        "KYC-02": ("KYC Documents", "Aadhar details"),
        "KYC-03": ("KYC Documents", "Passport details"),
        "KYC-04": ("KYC Documents", "Voter ID"),
        "KYC-05": ("KYC Documents", "Driving licence details"),
        "ID-01":  ("Identity Data", "Name"),
        "ID-13":  ("Identity Data", "Identification number (including Customer ID/Employee ID)"),
        "ID-04":  ("Identity Data", "Personal Phone Number"),
        "ID-07":  ("Identity Data", "Personal Email ID"),
        "BIO-01": ("Biometric Data", "Fingerprints"),
        "BIO-02": ("Biometric Data", "Voice patterns"),
        "ONL-01": ("Online Identifiers", "Username"),
        "ONL-02": ("Online Identifiers", "Passwords"),
        "ONL-03": ("Online Identifiers", "IP Address"),
        "ONL-04": ("Online Identifiers", "Cookie details (location, browsing patterns, etc.)"),
        "FIN-01": ("Financial Data", "Bank account numbers"),
        "FIN-02": ("Financial Data", "Debit Card details"),
        "FIN-04": ("Financial Data", "UPI Handles"),
        "FIN-05": ("Financial Data", "Account balance"),
        "FIN-06": ("Financial Data", "Account transaction history"),
        "CHD-01": ("Children and Person with Disability Data", "Child Name"),
        "CHD-02": ("Children and Person with Disability Data", "Child Date of Birth"),
    }

    for pid, status in pii_inventory.items():
        if status == "PRESENT" and pid in pii_to_inv:
            category, parameter = pii_to_inv[pid]
            if category not in inventory:
                inventory[category] = []
            inventory[category].append({
                "parameter": parameter,
                "response": "Yes",
                "mode_collection": "Digital",
                "mode_processing": "Digital",
            })

    return inventory
