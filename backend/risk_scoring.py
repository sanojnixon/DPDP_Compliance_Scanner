"""
risk_scoring.py - combines deterministic rules with AI reasoning.
"""

from typing import Any, Dict, List


SEVERITY_PENALTY = {
    "Critical": 18, "CRITICAL": 18,
    "High": 10, "HIGH": 10,
    "Medium": 5, "MEDIUM": 5,
    "Low": 2, "LOW": 2,
    "Info": 0, "INFO": 0,
    "None": 0,
}

DOCUMENT_SENSITIVITY = {
    "Bank Statement": 10,
    "Passbook Screen": 9,
    "KYC Form": 9,
    "Loan/Credit Screen": 8,
    "Account Summary": 8,
    "Transaction Receipt": 7,
    "Profile Screen": 7,
    "Insurance Document": 6,
    "Generic Banking Screen": 5,
    "Unknown/Other": 3,
}


def _level_from_score(score: int) -> str:
    if score >= 85:
        return "Low"
    if score >= 70:
        return "Medium"
    if score >= 45:
        return "High"
    return "Critical"


def _readiness_from_score(score: int) -> str:
    if score >= 85:
        return "Ready"
    if score >= 70:
        return "Mostly Ready"
    if score >= 45:
        return "Needs Remediation"
    return "Not Ready"


def compute_combined_risk(
    *,
    rule_compliance: Dict[str, Any],
    entities: List[Dict[str, Any]],
    ai_analysis: Dict[str, Any],
    document_type: str,
) -> Dict[str, Any]:
    base_score = 100  # No longer derived from rules engine scoring
    findings = ai_analysis.get("findings") or []
    ai_penalty = sum(SEVERITY_PENALTY.get(str(f.get("severity", "Low")), 2) for f in findings)

    unmasked_high_risk = sum(
        1 for entity in entities
        if not entity.get("masked") and entity.get("risk") in {"Critical", "High"}
    )
    sensitivity_penalty = DOCUMENT_SENSITIVITY.get(document_type, 3)

    combined_score = max(
        0,
        min(100, base_score - ai_penalty - (unmasked_high_risk * 3) - sensitivity_penalty),
    )

    severity = _level_from_score(combined_score)
    return {
        "score": combined_score,
        "severity": severity,
        "readiness": _readiness_from_score(combined_score),
        "ai_findings": len(findings),
        "document_sensitivity": sensitivity_penalty,
        "unmasked_high_risk_entities": unmasked_high_risk,
    }
