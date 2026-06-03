"""
pii_patterns.py — Layer 1: Regex / rule-based PII detection
============================================================
All patterns are compiled once at import time for efficiency.
Each detector function accepts a string and returns a list of RawMatch dicts.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RawMatch:
    pii_type: str           # e.g. "PAN", "AADHAAR", "EMAIL"
    value: str              # matched string (original, not normalised)
    start: int              # char offset in source text
    end: int                # char offset in source text
    confidence: float       # 0.0 – 1.0
    masked: bool = False    # True if value appears partially masked
    notes: str = ""         # optional debug note
    reason: str = ""        # explanation of detection
    source_rule: str = "Regex" # source of the match (e.g. "Regex", "Context")
    document_type: str = "" # context document type
    context: Dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Compiled regex catalogue
# ─────────────────────────────────────────────────────────────────────────────

_PATTERNS = {
    # ── KYC Documents ────────────────────────────────────────────────────────
    "PAN": re.compile(
        r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE
    ),
    "AADHAAR_UNMASKED": re.compile(
        r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
    ),
    "AADHAAR_MASKED": re.compile(
        r"\b[Xx*]{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
    ),
    "PASSPORT": re.compile(
        r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b", re.IGNORECASE
    ),
    "VOTER_ID": re.compile(
        r"\b[A-Z]{3}\d{7}\b", re.IGNORECASE
    ),
    "DRIVING_LICENCE": re.compile(
        r"\b[A-Z]{2}[\s\-]?\d{2}[\s\-]?\d{4}[\s\-]?\d{7}\b|"
        r"\b[A-Z]{2}\d{13}\b",
        re.IGNORECASE
    ),

    # ── Identity Data ─────────────────────────────────────────────────────────
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    "PHONE_IN": re.compile(
        r"(?<!\d)(\+91[\s\-]?)?[6-9]\d{9}(?!\d)"
    ),
    "DATE_OF_BIRTH": re.compile(
        r"\b(?:\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}"
        r"|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b"
    ),

    # ── Financial Data ────────────────────────────────────────────────────────
    "CREDIT_DEBIT_CARD": re.compile(
        r"\b(?:\d{4}[\s\-]){3}\d{4}\b"
    ),
    "MASKED_CARD": re.compile(
        r"\b[Xx*]{4}[\s\-][Xx*]{4}[\s\-][Xx*]{4}[\s\-]\d{4}\b"
    ),
    "BANK_ACCOUNT": re.compile(
        # 9-18 digit strings that are NOT a phone number or Aadhaar
        r"(?<![/\-\d])\b\d{9,18}\b(?![/\-\d])"
    ),
    "IFSC": re.compile(
        r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE
    ),
    "UPI_HANDLE": re.compile(
        r"\b[\w.\-]{2,256}@(?:okaxis|okicici|oksbi|okhdfc|ybl|ibl|axl"
        r"|upi|paytm|apl|airtel|jio|fbl|rbl|gpay|phonepe|razorpay"
        r"|[a-z]{2,20})\b",
        re.IGNORECASE
    ),

    # ── Online Identifiers ────────────────────────────────────────────────────
    "IP_ADDRESS": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
    ),

    # ── Keyword / reference detectors (lower confidence) ─────────────────────
    "_KW_PHOTOGRAPH": re.compile(
        r"\b(?:photograph|photo|selfie|portrait|face\s*image)\b", re.IGNORECASE
    ),
    "_KW_SIGNATURE": re.compile(
        r"\b(?:signature|sign|signed|countersign)\b", re.IGNORECASE
    ),
    "_KW_CCTV": re.compile(
        r"\b(?:cctv|surveillance|security\s*cam(?:era)?|video\s*recording)\b",
        re.IGNORECASE
    ),
    "_KW_VOICE": re.compile(
        r"\b(?:voice\s*recording|audio\s*clip|call\s*recording)\b", re.IGNORECASE
    ),
    "_KW_PASSWORD": re.compile(
        r"\b(?:password|passwd|pwd|passphrase)\b", re.IGNORECASE
    ),
    "_KW_COOKIE": re.compile(
        r"\b(?:cookie|session[\s_-]?id|auth[\s_-]?token|bearer)\b", re.IGNORECASE
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# Confidence table  (keyword patterns intentionally lower)
# ─────────────────────────────────────────────────────────────────────────────
_CONFIDENCE = {
    "PAN": 0.97,
    "AADHAAR_UNMASKED": 0.95,
    "AADHAAR_MASKED": 0.90,
    "PASSPORT": 0.88,
    "VOTER_ID": 0.85,
    "DRIVING_LICENCE": 0.82,
    "EMAIL": 0.92,
    "PHONE_IN": 0.88,
    "DATE_OF_BIRTH": 0.78,
    "CREDIT_DEBIT_CARD": 0.93,
    "MASKED_CARD": 0.90,
    "BANK_ACCOUNT": 0.72,   # lower — many false positives possible
    "IFSC": 0.96,
    "UPI_HANDLE": 0.90,
    "IP_ADDRESS": 0.94,
    "_KW_PHOTOGRAPH": 0.65,
    "_KW_SIGNATURE": 0.62,
    "_KW_CCTV": 0.68,
    "_KW_VOICE": 0.68,
    "_KW_PASSWORD": 0.70,
    "_KW_COOKIE": 0.65,
}

# Masked flags for pattern types
_MASKED_TYPES = {"AADHAAR_MASKED", "MASKED_CARD"}


# ─────────────────────────────────────────────────────────────────────────────
# Core detection function
# ─────────────────────────────────────────────────────────────────────────────

def detect_all(text: str) -> List[RawMatch]:
    """
    Run all patterns against `text` and return deduplicated RawMatch list.
    Bank account detection is post-filtered to suppress numbers already
    matched as Aadhaar/card/phone.
    """
    if not text or not text.strip():
        return []

    all_matches: List[RawMatch] = []
    occupied_spans: List[tuple] = []   # list of (start, end) already claimed

    def _is_overlapping(start: int, end: int) -> bool:
        for s, e in occupied_spans:
            if start < e and end > s:
                return True
        return False

    # Run patterns in priority order (specific first)
    priority_order = [
        "PAN", "AADHAAR_MASKED", "AADHAAR_UNMASKED",
        "CREDIT_DEBIT_CARD", "MASKED_CARD",
        "IFSC", "PASSPORT", "VOTER_ID", "DRIVING_LICENCE",
        "UPI_HANDLE", "EMAIL", "PHONE_IN", "IP_ADDRESS",
        "DATE_OF_BIRTH", "BANK_ACCOUNT",
        "_KW_CCTV", "_KW_VOICE", "_KW_PASSWORD",
        "_KW_COOKIE", "_KW_PHOTOGRAPH", "_KW_SIGNATURE",
    ]

    for pii_type in priority_order:
        pattern = _PATTERNS.get(pii_type)
        if not pattern:
            continue
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            if _is_overlapping(start, end):
                continue
            value = m.group(0).strip()
            masked = pii_type in _MASKED_TYPES
            match_obj = RawMatch(
                pii_type=pii_type,
                value=value,
                start=start,
                end=end,
                confidence=_CONFIDENCE.get(pii_type, 0.70),
                masked=masked,
                reason=f"Matched standard {pii_type} pattern",
                source_rule="Regex"
            )
            all_matches.append(match_obj)
            if pii_type != "AADHAAR_UNMASKED":
                occupied_spans.append((start, end))
            logger.debug(f"PII detected: {pii_type} → '{value}' at [{start}:{end}]")

    logger.info(f"Pattern scan complete: {len(all_matches)} raw matches found.")
    return all_matches


def detect_in_block(block_text: str, block_index: int) -> List[RawMatch]:
    """Convenience wrapper — detects PII in a single OCR block."""
    return detect_all(block_text)
