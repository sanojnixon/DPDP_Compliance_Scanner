"""
document_classifier.py — Document Type Classification Layer
===========================================================
Classifies the uploaded image/document into a specific type based on
OCR text, keywords, and structural cues.
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

DOC_TYPES = [
    "Bank Statement",
    "Transaction Receipt",
    "Account Summary",
    "KYC Form",
    "Passbook Screen",
    "Profile Screen",
    "Loan/Credit Screen",
    "Insurance Document",
    "Generic Banking Screen",
    "Unknown/Other"
]

def classify_document(ocr_blocks: List[Dict[str, Any]], full_text: str) -> str:
    """
    Classifies a document based on keyword heuristics.
    Returns one of the predefined document types.
    """
    text_lower = full_text.lower()
    
    # 1. Transaction Receipt
    receipt_kws = ["transaction successful", "payment details", "txn id", "txn no", "transaction id", "paid to", "received from", "payment successful", "ref no"]
    if any(kw in text_lower for kw in receipt_kws):
        # Additional check to differentiate from statement
        if "statement" not in text_lower:
            return "Transaction Receipt"

    # 2. Bank Statement
    stmt_kws = ["statement of account", "account statement", "opening balance", "closing balance", "narration", "withdrawal", "deposit"]
    # If it has 'statement' and some column headers like date, narration, amount
    if "statement" in text_lower and ("date" in text_lower or "balance" in text_lower):
        return "Bank Statement"
    if any(kw in text_lower for kw in stmt_kws):
        return "Bank Statement"

    # 3. Passbook Screen
    if "passbook" in text_lower or "m-passbook" in text_lower:
        return "Passbook Screen"

    # 4. Account Summary
    summary_kws = ["account summary", "available balance", "ledger balance", "lien amount", "total balance"]
    if any(kw in text_lower for kw in summary_kws):
        return "Account Summary"

    # 5. KYC Form
    kyc_kws = ["kyc", "customer information file", "know your customer", "nominee details", "fatca", "address proof"]
    if any(kw in text_lower for kw in kyc_kws):
        return "KYC Form"

    # 6. Profile Screen
    profile_kws = ["profile details", "personal details", "contact information", "edit profile", "my profile"]
    if any(kw in text_lower for kw in profile_kws):
        return "Profile Screen"

    # 7. Loan/Credit Screen
    loan_kws = ["loan account", "credit limit", "emi amount", "outstanding balance", "repayment", "loan summary"]
    if any(kw in text_lower for kw in loan_kws):
        return "Loan/Credit Screen"

    # 8. Insurance Document
    ins_kws = ["insurance policy", "premium amount", "policy number", "sum assured", "coverage details"]
    if any(kw in text_lower for kw in ins_kws):
        return "Insurance Document"

    # 9. Generic Banking Screen
    bank_kws = ["bank", "branch", "ifsc", "account number", "beneficiary"]
    # If it has several bank keywords but didn't match specific types
    bank_kw_count = sum(1 for kw in bank_kws if kw in text_lower)
    if bank_kw_count >= 2:
        return "Generic Banking Screen"

    return "Unknown/Other"
