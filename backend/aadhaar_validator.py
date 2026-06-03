"""
aadhaar_validator.py - Aadhaar-specific validation helpers.

Random 12 digit banking references must not be treated as Aadhaar. A high
confidence Aadhaar classification requires formatting checks, contextual
support, and a valid Verhoeff checksum.
"""

import re
from typing import Any, Dict, Iterable


_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

AADHAAR_CONTEXT_KEYWORDS = {
    "aadhaar",
    "aadhar",
    "uid",
    "uidai",
    "vid",
    "ekyc",
    "kyc",
    "identity proof",
    "id proof",
}

BANKING_CONTEXT_KEYWORDS = {
    "upi",
    "txn",
    "transaction",
    "ref",
    "reference",
    "utr",
    "transfer",
    "payment",
    "sibl",
    "yesb",
    "sbin",
    "ubin",
    "neft",
    "rtgs",
    "imps",
    "debit",
    "credit",
    "balance",
    "narration",
}


def normalize_aadhaar_candidate(value: str) -> str:
    return re.sub(r"[\s-]", "", value or "")


def verhoeff_is_valid(number: str) -> bool:
    if not re.fullmatch(r"\d+", number or ""):
        return False
    checksum = 0
    for idx, digit in enumerate(reversed(number)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[idx % 8][int(digit)]]
    return checksum == 0


def _keyword_hits(text: str, keywords: Iterable[str]) -> list[str]:
    lower_text = (text or "").lower()
    return [keyword for keyword in keywords if keyword in lower_text]


def validate_aadhaar_candidate(value: str, context_text: str = "") -> Dict[str, Any]:
    digits = normalize_aadhaar_candidate(value)
    aadhaar_hits = _keyword_hits(context_text, AADHAAR_CONTEXT_KEYWORDS)
    banking_hits = _keyword_hits(context_text, BANKING_CONTEXT_KEYWORDS)

    format_valid = bool(re.fullmatch(r"\d{12}", digits))
    starts_valid = bool(format_valid and digits[0] not in {"0", "1"})
    repeated_digit = bool(format_valid and len(set(digits)) == 1)
    checksum_valid = bool(format_valid and verhoeff_is_valid(digits))
    context_supported = bool(aadhaar_hits)
    banking_context = bool(banking_hits)

    confidence = 0.0
    reasons = []
    if format_valid:
        confidence += 0.30
        reasons.append("12 digit format")
    else:
        reasons.append("not a 12 digit unmasked Aadhaar candidate")
    if starts_valid:
        confidence += 0.10
    else:
        reasons.append("invalid Aadhaar leading digit")
    if checksum_valid:
        confidence += 0.45
        reasons.append("valid Verhoeff checksum")
    else:
        reasons.append("failed Verhoeff checksum")
    if context_supported:
        confidence += 0.15
        reasons.append(f"Aadhaar context: {', '.join(aadhaar_hits[:4])}")
    if banking_context:
        confidence -= 0.45
        reasons.append(f"banking transaction context: {', '.join(banking_hits[:5])}")
    if repeated_digit:
        confidence -= 0.30
        reasons.append("repeated digit sequence")

    confidence = max(0.0, min(0.99, confidence))
    is_valid = bool(format_valid and starts_valid and checksum_valid and not repeated_digit)

    return {
        "normalized": digits,
        "format_valid": format_valid,
        "starts_valid": starts_valid,
        "checksum_valid": checksum_valid,
        "context_supported": context_supported,
        "banking_context": banking_context,
        "context_keywords": aadhaar_hits,
        "banking_keywords": banking_hits,
        "confidence": round(confidence, 4),
        "is_valid": is_valid,
        "reason": "; ".join(reasons),
    }
