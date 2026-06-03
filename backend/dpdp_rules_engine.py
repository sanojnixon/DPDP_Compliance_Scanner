"""
dpdp_rules_engine.py — DPDP Compliance Rules Engine (PART C–G)
Implements the 8-step evaluation from DPDP_Rules_Engine.md.
Replaces the deprecated pii_rules.py masking-only checks.
"""
import re, logging
from typing import Any, Dict, List, Optional, Set
from dpdp_pii_registry import scan_pii_inventory, get_present_pii_ids, get_pii_name
from dpdp_screen_classifier import classify_screen_types

logger = logging.getLogger(__name__)

# PART D — Rule Applicability Matrix
RULE_APPLICABILITY: Dict[str, Set[str]] = {
    "RULE-DM-01": {"SCR-02"},
    "RULE-DM-02": {"SCR-04"},
    "RULE-DM-03": {"SCR-01","SCR-02","SCR-07","SCR-09"},
    "RULE-DM-04": {"SCR-06"},
    "RULE-DM-05": {"SCR-07"},
    "RULE-DM-06": {"SCR-07"},
    "RULE-CN-01": {"SCR-01","SCR-09"},
    "RULE-CN-02": {"SCR-10"},
    "RULE-CN-03": {"SCR-10"},
    "RULE-CN-04": {"SCR-10"},
    "RULE-CN-05": {"SCR-05","SCR-06"},
    "RULE-CN-06": {"SCR-11"},
    "RULE-SEC-01": {"SCR-13"},
    "RULE-SEC-02": {"SCR-03"},
    "RULE-SEC-03": {"SCR-12"},
    "RULE-SEC-04": {"SCR-13"},
    "RULE-SEC-05": {"SCR-01","SCR-09"},
    "RULE-RET-01": {"SCR-03"},
    "RULE-RET-02": {"SCR-02","SCR-03"},
    "RULE-CHD-01": {"SCR-01","SCR-02","SCR-07"},
    "RULE-CHD-02": {"SCR-02","SCR-11"},
    "RULE-CHD-03": {"SCR-02","SCR-11"},
    "RULE-TP-01":  {"SCR-11"},
    "RULE-TP-02":  {"SCR-11"},
    "RULE-SEN-01": {"SCR-02","SCR-03","SCR-04","SCR-05","SCR-06"},
    "RULE-SEN-02": {"SCR-02","SCR-03","SCR-04","SCR-05","SCR-06"},
    "RULE-SEN-03": {"SCR-09"},
    "RULE-GR-01":  {"SCR-01","SCR-07","SCR-09"},
    "RULE-ACC-01": {"SCR-01","SCR-02","SCR-07"},
}

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# Section title lookup for human-readable output
SECTION_TITLES = {
    "Section 4": "Grounds for processing",
    "Section 5(1)": "Notice",
    "Section 5(1)(i)": "Purpose in notice",
    "Section 5(1)(ii)": "Rights in notice",
    "Section 6": "Consent",
    "Section 6(1)": "Consent requirements / Data minimisation",
    "Section 8(3)": "Data accuracy",
    "Section 8(5)": "Security safeguards",
    "Section 8(7)": "Data retention and erasure",
    "Section 8(9)": "DPO contact publication",
    "Section 8(10)": "Grievance redressal mechanism",
    "Section 9(1)": "Verifiable parental consent",
    "Section 9(3)": "No tracking/targeting children",
}

# Penalty reference lookup per section
PENALTY_REFERENCE = {
    "Section 8(5)": "Up to \u20b9250 crore",
    "Section 8(6)": "Up to \u20b9200 crore",
    "Section 9": "Up to \u20b9200 crore",
    "Section 9(1)": "Up to \u20b9200 crore",
    "Section 9(3)": "Up to \u20b9200 crore",
    "Section 10": "Up to \u20b9150 crore",
}


def _v(rule_id, pii_ids, section, finding, severity):
    """Build a violation detail dict."""
    return {
        "rule_id": rule_id,
        "pii_involved": pii_ids if isinstance(pii_ids, list) else [pii_ids],
        "act_section": section,
        "section_title": SECTION_TITLES.get(section, ""),
        "finding": finding,
        "severity": severity,
        "penalty_reference": PENALTY_REFERENCE.get(section, "Up to \u20b950 crore"),
    }


def _has(p, *ids):
    """Check if any of the given PII IDs are PRESENT."""
    return any(p.get(i) == "PRESENT" for i in ids)


def _count_visible_unmasked(entities, pii_ids_set):
    """Count entities mapping to given PII IDs that are unmasked."""
    from dpdp_pii_registry import ENTITY_TO_PII_IDS
    c = 0
    for e in entities:
        if e.get("masked"):
            continue
        mapped = ENTITY_TO_PII_IDS.get(e.get("raw_type", ""), [])
        if any(m in pii_ids_set for m in mapped):
            c += 1
    return c


# ── Individual Rule Checks ────────────────────────────────────────────────

def _dm01(p, entities, txt):
    target = {"FIN-01","ID-01","ID-14","ID-13","KYC-01","KYC-02","FIN-07"}
    visible = {pid for pid in target if p.get(pid) == "PRESENT"}
    unmasked = _count_visible_unmasked(entities, target)
    if len(visible) > 3 and unmasked > 3:
        return _v("RULE-DM-01", sorted(visible), "Section 6(1)",
                   f"Dashboard displays {len(visible)} unmasked PII fields simultaneously, exceeding data minimisation limits.", "HIGH")

def _dm02(p, entities, txt):
    from dpdp_pii_registry import ENTITY_TO_PII_IDS
    for e in entities:
        rt = e.get("raw_type", "")
        if rt == "CREDIT_DEBIT_CARD" and not e.get("masked"):
            return _v("RULE-DM-02", ["FIN-02"], "Section 6(1)",
                       "Full 16-digit card number visible unmasked on card info screen.", "CRITICAL")
    # Check CVV
    if re.search(r"\bcvv\b\s*[:\-]?\s*\d{3}\b", txt, re.I):
        return _v("RULE-DM-02", ["FIN-02"], "Section 6(1)",
                   "CVV value appears visible on card info screen.", "CRITICAL")

def _dm03(p, entities, txt):
    for e in entities:
        if e.get("raw_type") == "AADHAAR_UNMASKED" and not e.get("masked"):
            return _v("RULE-DM-03", ["KYC-02"], "Section 6(1)",
                       f"Full Aadhaar number '{e.get('value','')}' displayed unmasked; must show only last 4 digits.", "CRITICAL")

def _dm04(p, entities, txt):
    excess = [pid for pid in ["KYC-01","KYC-02","ID-04","ID-07","FIN-01"] if p.get(pid) == "PRESENT"]
    if excess:
        return _v("RULE-DM-04", excess, "Section 6(1)",
                   "Recharge screen shows data beyond mobile number and amount.", "MEDIUM")

def _dm05(p, entities, txt):
    excess = [pid for pid in ["FIN-09","FIN-11","FIN-10"] if p.get(pid) == "PRESENT"]
    if excess:
        return _v("RULE-DM-05", excess, "Section 6(1)",
                   "Income/CTC/tax data visible on non-loan screen.", "HIGH")

def _dm06(p, entities, txt):
    sensitive = [pid for pid in ["ID-17","ID-18","ID-20","CHD-04"] if p.get(pid) == "PRESENT"]
    if sensitive:
        return _v("RULE-DM-06", sensitive, "Section 6(1)",
                   "Sensitive attributes (religion/caste/disability) visible on profile screen without lawful purpose.", "HIGH")

def _cn01(p, entities, txt):
    tl = txt.lower()
    consent_terms = ["i agree", "consent", "purpose of processing", "withdraw consent", "i accept"]
    if not any(t in tl for t in consent_terms):
        pii_present = [pid for pid in ["KYC-01","KYC-02","KYC-03"] if p.get(pid) == "PRESENT"]
        if not pii_present:
            pii_present = ["KYC-02"]
        return _v("RULE-CN-01", pii_present, "Section 5(1)",
                   "KYC/onboarding screen collects PII but no consent notice is visible.", "CRITICAL")

def _cn02(p, entities, txt):
    tl = txt.lower()
    if not any(w in tl for w in ["purpose", "why we collect", "used for", "processing for"]):
        return _v("RULE-CN-02", [], "Section 5(1)(i)",
                   "Consent banner lacks a purpose statement describing what data will be used for.", "HIGH")

def _cn03(p, entities, txt):
    tl = txt.lower()
    if not any(w in tl for w in ["withdraw consent", "right to withdraw", "revoke consent"]):
        return _v("RULE-CN-03", [], "Section 5(1)(ii)",
                   "Consent banner does not mention consent withdrawal rights.", "HIGH")

def _cn04(p, entities, txt):
    tl = txt.lower()
    blanket = ["agree to all terms", "consent to use of all your data", "consent to sharing with partners",
               "agree to all", "consent to all"]
    if any(b in tl for b in blanket):
        return _v("RULE-CN-04", [], "Section 6(1)",
                   "Blanket consent clause detected without specifying data or purpose.", "HIGH")

def _cn05(p, entities, txt):
    tl = txt.lower()
    excess = any(w in tl for w in ["contacts", "location access", "camera access", "gallery", "email access"])
    if excess:
        return _v("RULE-CN-05", [], "Section 6(1)",
                   "Consent requested for data beyond transaction necessity (contacts/location/camera).", "MEDIUM")

def _cn06(p, entities, txt):
    tl = txt.lower()
    pii_visible = _has(p, "ID-01","ID-14","FIN-01","FIN-07")
    no_optout = not any(w in tl for w in ["opt out", "opt-out", "decline", "no thanks", "manage preferences"])
    if pii_visible and no_optout:
        pii = [pid for pid in ["ID-01","ID-14","FIN-01","FIN-07"] if p.get(pid) == "PRESENT"]
        return _v("RULE-CN-06", pii, "Section 6",
                   "PII visible alongside third-party content with no opt-out control.", "HIGH")

def _sec01(p, entities, txt):
    for e in entities:
        if e.get("raw_type") == "_KW_PASSWORD" and not e.get("masked"):
            return _v("RULE-SEC-01", ["ONL-02"], "Section 8(5)",
                       "Password or credential visible in plaintext.", "CRITICAL")

def _sec02(p, entities, txt):
    for e in entities:
        if e.get("raw_type") == "BANK_ACCOUNT" and not e.get("masked"):
            return _v("RULE-SEC-02", ["FIN-01"], "Section 8(5)",
                       f"Full account number '{e.get('value','')}' unmasked in transaction history.", "HIGH")

def _sec03(p, entities, txt):
    tl = txt.lower()
    signals = ["stack trace", "traceback", "internal api", "raw database", "exception"]
    debug = [s for s in signals if s in tl]
    if debug or _has(p, "ONL-03", "ONL-04"):
        pii = ["ONL-03","ONL-04"] if _has(p,"ONL-03","ONL-04") else []
        return _v("RULE-SEC-03", pii, "Section 8(5)",
                   "Internal system data or debug info exposed on user-facing screen.", "CRITICAL")

def _sec04(p, entities, txt):
    otp_match = re.search(r"\b(?:otp|one.time.password)\b.*?\b(\d{4,8})\b", txt, re.I)
    if otp_match:
        return _v("RULE-SEC-04", [], "Section 8(5)",
                   "OTP or authentication token visible in plaintext after auth step.", "HIGH")

def _sec05(p, entities, txt):
    tl = txt.lower()
    bio = _has(p, "BIO-01", "BIO-02")
    indicator = any(w in tl for w in ["biometric authentication", "biometric capture", "fingerprint scan"])
    if bio and not indicator:
        return _v("RULE-SEC-05", ["BIO-01","BIO-02"], "Section 8(5)",
                   "Biometric capture detected without explicit on-screen indicator.", "CRITICAL")

def _ret01(p, entities, txt):
    kyc_in_txn = any(p.get(pid) == "PRESENT" for pid in ["KYC-01","KYC-02","KYC-03","KYC-04","KYC-05"])
    if kyc_in_txn:
        pii = [pid for pid in ["KYC-01","KYC-02","KYC-03","KYC-04","KYC-05"] if p.get(pid) == "PRESENT"]
        return _v("RULE-RET-01", pii, "Section 8(7)",
                   "KYC document data visible in transaction history with no current purpose.", "MEDIUM")

def _ret02(p, entities, txt):
    tl = txt.lower()
    closed = any(w in tl for w in ["closed", "dormant", "inactive", "account closed"])
    if closed:
        exposed = [pid for pid in ["FIN-01","ID-01","ID-07","FIN-07"] if p.get(pid) == "PRESENT"]
        if exposed:
            return _v("RULE-RET-02", exposed, "Section 8(7)",
                       "Full PII for closed/dormant account still visible without masking.", "MEDIUM")

def _chd01(p, entities, txt):
    tl = txt.lower()
    child = _has(p, "CHD-01", "CHD-02")
    guardian = any(w in tl for w in ["guardian", "parent consent", "minor account", "guardian authorised"])
    if child and not guardian:
        return _v("RULE-CHD-01", ["CHD-01"], "Section 9(1)",
                   "Minor account detected without visible guardian consent indicator.", "CRITICAL")

def _chd02(p, entities, txt):
    child = _has(p, "CHD-01", "CHD-02")
    if child:
        return _v("RULE-CHD-02", ["CHD-01"], "Section 9(3)",
                   "Third-party offer/ad content visible on a minor's account screen.", "CRITICAL")

def _chd03(p, entities, txt):
    tl = txt.lower()
    child = _has(p, "CHD-01", "CHD-02")
    tracking = any(w in tl for w in ["personalised", "recommended for you", "based on your activity"])
    if child and tracking:
        return _v("RULE-CHD-03", ["CHD-01"], "Section 9(3)",
                   "Behavioural tracking indicator detected on child account screen.", "CRITICAL")

def _tp01(p, entities, txt):
    pii_visible = _has(p, "ID-01","ID-14","FIN-07","FIN-08")
    if pii_visible:
        pii = [pid for pid in ["ID-01","ID-14","FIN-07","FIN-08"] if p.get(pid) == "PRESENT"]
        return _v("RULE-TP-01", pii, "Section 4",
                   "Customer PII embedded within or adjacent to third-party promotional content.", "HIGH")

def _tp02(p, entities, txt):
    tl = txt.lower()
    has_name = p.get("ID-01") == "PRESENT"
    no_disclosure = not any(w in tl for w in ["data sharing", "shared with", "data shared"])
    if has_name and no_disclosure:
        return _v("RULE-TP-02", ["ID-01"], "Section 5(1)",
                   "Customer name referenced alongside third-party brand with no data sharing disclosure.", "HIGH")

def _sen01(p, entities, txt):
    sensitive = [pid for pid in ["ID-17","ID-18","ID-20"] if p.get(pid) == "PRESENT"]
    if sensitive:
        return _v("RULE-SEN-01", sensitive, "Section 4",
                   "Religion/caste data visible on standard banking screen without lawful purpose.", "HIGH")

def _sen02(p, entities, txt):
    bio = _has(p, "BIO-01", "BIO-02")
    if bio:
        return _v("RULE-SEN-02", ["BIO-01","BIO-02"], "Section 6(1)",
                   "Biometric data displayed on unrelated banking screen.", "CRITICAL")

def _sen03(p, entities, txt):
    tl = txt.lower()
    bio = _has(p, "BIO-01", "BIO-02") or p.get("OTH-02") == "PRESENT"
    consent = any(w in tl for w in ["consent", "i agree", "i authorize", "permission"])
    if bio and not consent:
        return _v("RULE-SEN-03", ["BIO-01","OTH-02"], "Section 5(1)",
                   "Video KYC collects biometric data without visible consent statement.", "CRITICAL")

def _gr01(p, entities, txt):
    tl = txt.lower()
    present_count = sum(1 for pid in p if p[pid] == "PRESENT")
    grievance = any(w in tl for w in ["grievance", "dpo", "data protection officer",
                                       "raise concern", "complaint", "nodal officer"])
    if present_count >= 3 and not grievance:
        return _v("RULE-GR-01", [], "Section 8(10)",
                   "PII-heavy screen lacks DPO contact or grievance redressal link.", "LOW")

def _acc01(p, entities, txt):
    from dpdp_pii_registry import ENTITY_TO_PII_IDS
    type_values: Dict[str, List[str]] = {}
    for e in entities:
        rt = e.get("raw_type", "")
        val = e.get("value", "")
        if rt in ("PHONE_IN", "EMAIL", "ACCOUNT_HOLDER_NAME", "BANK_ACCOUNT"):
            type_values.setdefault(rt, []).append(val)
    for rt, vals in type_values.items():
        unique = set(vals)
        if len(unique) > 1:
            pii_ids = ENTITY_TO_PII_IDS.get(rt, [])
            return _v("RULE-ACC-01", pii_ids, "Section 8(3)",
                       f"Conflicting {rt} values on same screen: {', '.join(sorted(unique)[:3])}.", "MEDIUM")


# Rule ID → checker function
_RULE_CHECKERS = {
    "RULE-DM-01": _dm01, "RULE-DM-02": _dm02, "RULE-DM-03": _dm03,
    "RULE-DM-04": _dm04, "RULE-DM-05": _dm05, "RULE-DM-06": _dm06,
    "RULE-CN-01": _cn01, "RULE-CN-02": _cn02, "RULE-CN-03": _cn03,
    "RULE-CN-04": _cn04, "RULE-CN-05": _cn05, "RULE-CN-06": _cn06,
    "RULE-SEC-01": _sec01, "RULE-SEC-02": _sec02, "RULE-SEC-03": _sec03,
    "RULE-SEC-04": _sec04, "RULE-SEC-05": _sec05,
    "RULE-RET-01": _ret01, "RULE-RET-02": _ret02,
    "RULE-CHD-01": _chd01, "RULE-CHD-02": _chd02, "RULE-CHD-03": _chd03,
    "RULE-TP-01": _tp01, "RULE-TP-02": _tp02,
    "RULE-SEN-01": _sen01, "RULE-SEN-02": _sen02, "RULE-SEN-03": _sen03,
    "RULE-GR-01": _gr01, "RULE-ACC-01": _acc01,
}


# ── PART F — Inconclusive Conditions ──────────────────────────────────────

def _check_inconclusive(screen_cls, pii_inv, entities, txt, avg_conf):
    reasons = []
    if screen_cls.get("confidence") == "low":
        reasons.append("Screen type could not be determined with confidence from OCR text alone.")
    if avg_conf < 0.4:
        reasons.append(f"Average OCR confidence is very low ({avg_conf:.2f}); PII detection may be unreliable.")
    # Partial masking ambiguity
    for e in entities:
        if e.get("raw_type") in ("CREDIT_DEBIT_CARD", "MASKED_CARD"):
            val = re.sub(r"[\s\-]", "", e.get("value", ""))
            visible_digits = sum(1 for c in val if c.isdigit())
            if 4 < visible_digits < 16:
                reasons.append(f"Card number partially visible ({visible_digits} digits); masking compliance cannot be confirmed.")
                break
    return reasons


# ── Main Evaluator (PART G — 8 Steps) ────────────────────────────────────

def evaluate_dpdp_compliance(
    *,
    ocr_full_text: str,
    ocr_blocks: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    avg_ocr_confidence: float = 0.0,
) -> Dict[str, Any]:
    """
    Execute the 8-step DPDP evaluation checklist from PART G.
    Returns a structured verdict.
    """
    # Step 1: Classify screen type (PART B)
    screen_cls = classify_screen_types(ocr_blocks, ocr_full_text)
    screen_types = set(screen_cls["screen_types"])

    # Step 2: Scan PII inventory (PART A)
    pii_inv = scan_pii_inventory(entities, ocr_full_text)

    # Step 3: Identify applicable rules (PART D)
    applicable_rules = []
    for rule_id, applicable_screens in RULE_APPLICABILITY.items():
        if screen_types & applicable_screens:
            applicable_rules.append(rule_id)

    # Step 4 & 5: Evaluate trigger conditions and confirm violations
    violations: List[Dict[str, Any]] = []
    for rule_id in applicable_rules:
        checker = _RULE_CHECKERS.get(rule_id)
        if not checker:
            continue
        result = checker(pii_inv, entities, ocr_full_text)
        if result:
            violations.append(result)

    # Step 6: Severity is assigned within each rule checker (PART E)

    # Step 7: Check inconclusive conditions (PART F)
    inconclusive_reasons = _check_inconclusive(screen_cls, pii_inv, entities, ocr_full_text, avg_ocr_confidence)

    # Step 8: Build structured verdict
    if inconclusive_reasons and not violations:
        verdict = "INCONCLUSIVE"
    elif violations:
        verdict = "YES"
    else:
        verdict = "NO"

    # Overall severity = worst among violations
    overall_severity = None
    if violations:
        best = min(violations, key=lambda v: SEVERITY_ORDER.get(v["severity"], 99))
        overall_severity = best["severity"]

    # Risk breakdown from entities
    by_risk = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for e in entities:
        r = e.get("risk", "Low")
        if r in by_risk:
            by_risk[r] += 1

    notes = []
    if inconclusive_reasons:
        notes.extend(inconclusive_reasons)

    logger.info(
        "[DPDP Rules Engine] verdict=%s violations=%d severity=%s screen=%s",
        verdict, len(violations), overall_severity, screen_cls["screen_type_label"],
    )

    return {
        # Structured verdict
        "screen_type": screen_cls["screen_type_label"],
        "screen_types": screen_cls["screen_types"],
        "screen_classification": screen_cls,
        "pii_inventory": pii_inv,
        "rules_evaluated": applicable_rules,
        "violations_found": verdict,
        "violation_details": violations,
        "overall_severity": overall_severity,
        "notes": notes,
        "total_entities": len(entities),
        "by_risk": by_risk,
    }
