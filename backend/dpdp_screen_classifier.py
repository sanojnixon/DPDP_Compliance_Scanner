"""
dpdp_screen_classifier.py — PART B Screen Type Classification
==============================================================
Classifies banking app screenshots into one or more of the 13 screen
types defined in DPDP_Rules_Engine.md PART B.

Returns a list of matching screen type IDs (a screen may match multiple).
Also returns a backward-compatible document_type string.
"""

import re
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

SCREEN_TYPES: Dict[str, str] = {
    "SCR-01": "KYC / Onboarding",
    "SCR-02": "Account Summary / Dashboard",
    "SCR-03": "Transaction History",
    "SCR-04": "Debit/Credit Card Info",
    "SCR-05": "Fund Transfer / Payment",
    "SCR-06": "Mobile Recharge",
    "SCR-07": "Profile / Settings",
    "SCR-08": "Loan / Credit Application",
    "SCR-09": "Video KYC",
    "SCR-10": "Notification / Consent Banner",
    "SCR-11": "Third-Party Offer / Ad",
    "SCR-12": "Error / Debug Screen",
    "SCR-13": "Login / Auth",
}

# Each screen type has keyword signals; order matters (more specific first)
_SCREEN_SIGNALS: List[Tuple[str, List[str]]] = [
    ("SCR-09", ["video kyc", "video feed", "face capture", "video verification"]),
    ("SCR-13", ["login", "sign in", "signin", "otp", "password", "authenticate", "enter pin"]),
    ("SCR-12", ["stack trace", "traceback", "error code", "debug", "internal server", "exception"]),
    ("SCR-10", ["consent", "i agree", "accept", "decline", "terms and conditions",
                "privacy policy", "withdraw consent", "permission"]),
    ("SCR-11", ["offer", "promotional", "partner", "sponsored", "advertisement",
                "apply now", "exclusive deal", "cashback offer"]),
    ("SCR-06", ["recharge", "mobile recharge", "prepaid", "operator", "talktime"]),
    ("SCR-04", ["card number", "card no", "cvv", "expiry", "debit card", "credit card",
                "card details", "card ending"]),
    ("SCR-01", ["kyc", "know your customer", "verify identity", "aadhaar",
                "pan verification", "address proof", "identity verification",
                "onboarding", "e-kyc", "ckyc", "fatca"]),
    ("SCR-08", ["loan", "emi", "credit limit", "outstanding", "repayment",
                "loan summary", "credit application", "pre-approved"]),
    ("SCR-05", ["fund transfer", "neft", "rtgs", "imps", "beneficiary", "ifsc",
                "transfer to", "send money", "pay to", "upi transfer"]),
    ("SCR-03", ["transaction history", "mini statement", "passbook", "recent transactions",
                "statement of account", "account statement", "narration",
                "opening balance", "closing balance", "dr", "cr",
                "withdrawal", "deposit", "debit", "credit"]),
    ("SCR-07", ["profile", "personal details", "contact information", "edit profile",
                "my profile", "settings", "preferences", "update details"]),
    ("SCR-02", ["account summary", "available balance", "balance", "account no",
                "dashboard", "total balance", "savings account",
                "current account", "ledger balance"]),
]

# Legacy document_type mapping for backward compatibility
_SCR_TO_LEGACY: Dict[str, str] = {
    "SCR-01": "KYC Form",
    "SCR-02": "Account Summary",
    "SCR-03": "Bank Statement",
    "SCR-04": "Generic Banking Screen",
    "SCR-05": "Transaction Receipt",
    "SCR-06": "Generic Banking Screen",
    "SCR-07": "Profile Screen",
    "SCR-08": "Loan/Credit Screen",
    "SCR-09": "KYC Form",
    "SCR-10": "Generic Banking Screen",
    "SCR-11": "Generic Banking Screen",
    "SCR-12": "Unknown/Other",
    "SCR-13": "Generic Banking Screen",
}


def classify_screen_types(
    ocr_blocks: List[Dict[str, Any]],
    full_text: str,
) -> Dict[str, Any]:
    """
    Classify the screenshot into PART B screen types.

    Returns:
        {
            "screen_types": ["SCR-02", "SCR-03"],
            "primary_screen_type": "SCR-03",
            "screen_type_label": "SCR-03 (Transaction History)",
            "document_type": "Bank Statement",  # legacy compat
            "confidence": "high" | "medium" | "low",
        }
    """
    text_lower = full_text.lower()
    matched: List[Tuple[str, int]] = []

    for scr_id, keywords in _SCREEN_SIGNALS:
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            matched.append((scr_id, hits))

    matched.sort(key=lambda x: x[1], reverse=True)
    screen_types = [scr_id for scr_id, _ in matched]

    if not screen_types:
        confidence = "low"
        screen_types = ["SCR-02"]  # default fallback
    elif matched[0][1] >= 3:
        confidence = "high"
    elif matched[0][1] >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    primary = screen_types[0]
    label = f"{primary} ({SCREEN_TYPES.get(primary, 'Unknown')})"
    legacy_doc_type = _SCR_TO_LEGACY.get(primary, "Unknown/Other")

    logger.info(
        "[Screen Classifier] primary=%s types=%s confidence=%s",
        primary, screen_types, confidence,
    )

    return {
        "screen_types": screen_types,
        "primary_screen_type": primary,
        "screen_type_label": label,
        "document_type": legacy_doc_type,
        "confidence": confidence,
    }


def get_screen_label(scr_id: str) -> str:
    """Return human-readable label for a screen type ID."""
    name = SCREEN_TYPES.get(scr_id, "Unknown")
    return f"{scr_id} ({name})"
