"""
pii_rules.py — Layer 3: DPDP Compliance Rule Engine
====================================================
Validates detected PII entities against DPDP data minimisation and masking
obligations. Returns a compliance report ready for API response.
"""

import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Individual masking checks
# ─────────────────────────────────────────────────────────────────────────────

def _is_aadhaar_masked(value: str) -> bool:
    """Return True only if the first 8 digits are masked/hidden."""
    cleaned = re.sub(r"[\s\-]", "", value)
    if len(cleaned) < 8:
        return False
    first_eight = cleaned[:8]
    return bool(re.match(r"[Xx*]{8}", first_eight))


def _is_card_masked(value: str) -> bool:
    """Return True if the card number is masked except last 4 digits."""
    cleaned = re.sub(r"[\s\-]", "", value)
    if len(cleaned) < 12:
        return False
    masked_part = cleaned[:-4]
    return bool(re.match(r"[Xx*]+", masked_part))


def _is_account_partially_masked(value: str) -> bool:
    """Return True if at least the first half of the account number is masked."""
    if len(value) < 6:
        return False
    half = len(value) // 2
    return bool(re.match(r"[Xx*]+", value[:half]))


# ─────────────────────────────────────────────────────────────────────────────
# Compliance flags per entity
# ─────────────────────────────────────────────────────────────────────────────

_RISK_WEIGHT = {"Critical": 25, "High": 10, "Medium": 4, "Low": 1, "None": 0}

def _flag_entity(entity: Dict[str, Any]) -> List[str]:
    """Generate DPDP compliance violation messages for a single entity."""
    flags = []
    raw_type = entity.get("raw_type", "")
    value = entity.get("value", "")
    masked = entity.get("masked", False)

    if raw_type == "AADHAAR_UNMASKED":
        flags.append(
            f"⚠ DPDP Violation: Aadhaar number fully visible — "
            f"must display only last 4 digits ('{value}')."
        )

    if raw_type == "CREDIT_DEBIT_CARD" and not _is_card_masked(value):
        flags.append(
            f"⚠ DPDP Violation: Full credit/debit card number exposed — "
            f"must mask first 12 digits ('{value}')."
        )

    if raw_type == "BANK_ACCOUNT" and not _is_account_partially_masked(value):
        flags.append(
            f"⚠ DPDP Violation: Bank account number '{value}' should show "
            f"only last 4 digits."
        )

    if raw_type == "_KW_PASSWORD":
        flags.append(
            f"⚠ DPDP Violation: Document contains a password reference — "
            f"credentials must never appear in unencrypted documents."
        )

    if raw_type == "PAN" and not masked:
        flags.append(
            f"ℹ DPDP Guidance: PAN number '{value}' is fully visible. "
            f"Consider masking first 5 characters for non-essential contexts."
        )

    if raw_type == "PHONE_IN":
        flags.append(
            f"ℹ DPDP Guidance: Phone number '{value}' detected. "
            f"Ensure consent exists for its collection and storage."
        )

    if raw_type == "ACCOUNT_BALANCE":
        flags.append(
            f"ℹ DPDP Guidance: Account balance detected. "
            f"Financial data requires strict access controls."
        )

    if raw_type == "TRANSACTION_HISTORY":
        flags.append(
            f"⚠ DPDP Violation: Transaction history detected. "
            f"This represents highly sensitive financial activity."
        )

    return flags


# ─────────────────────────────────────────────────────────────────────────────
# Compliance score
# ─────────────────────────────────────────────────────────────────────────────

def compute_compliance_score(entities: List[Dict[str, Any]]) -> int:
    """
    Compute a 0-100 compliance score.
    100 = no PII detected or all properly masked.
    Score decreases based on risk weight of each unmasked entity.
    """
    if not entities:
        return 100

    penalty = 0
    for e in entities:
        risk = e.get("risk", "Low")
        masked = e.get("masked", False)
        weight = _RISK_WEIGHT.get(risk, 0)
        # Masked entities still incur partial penalty (presence, not exposure)
        if masked:
            penalty += weight * 0.25
        else:
            penalty += weight

    score = max(0, 100 - int(penalty))
    return score


# ─────────────────────────────────────────────────────────────────────────────
# Risk breakdown
# ─────────────────────────────────────────────────────────────────────────────

def risk_breakdown(entities: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count entities by risk level."""
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "None": 0}
    for e in entities:
        risk = e.get("risk", "Low")
        counts[risk] = counts.get(risk, 0) + 1
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_compliance_report(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build the full compliance report for the API response.

    Returns:
        {
          "score": int,          # 0-100
          "grade": str,          # A/B/C/D/F
          "flags": [str],        # violation messages
          "total_entities": int,
          "by_risk": {Critical, High, Medium, Low}
        }
    """
    score = compute_compliance_score(entities)

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    all_flags: List[str] = []
    for entity in entities:
        all_flags.extend(_flag_entity(entity))

    by_risk = risk_breakdown(entities)

    report = {
        "score": score,
        "grade": grade,
        "flags": all_flags,
        "total_entities": len(entities),
        "by_risk": by_risk,
    }

    logger.info(
        f"Compliance report: score={score} ({grade}), "
        f"flags={len(all_flags)}, entities={len(entities)}, "
        f"by_risk={by_risk}"
    )
    return report
