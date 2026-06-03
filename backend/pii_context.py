"""
pii_context.py — Context Analysis and Entity Extraction Layer
=============================================================
Moves beyond pure regex matching to extract entities based on nearby labels,
banking keywords, screen context, and document type.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from pii_patterns import RawMatch
from banking_context import detect_transaction_context
from layout_mapping import extract_layout_entities

logger = logging.getLogger(__name__)

# Compile regexes for contextual cues
_RE_BALANCE = re.compile(r"(?:account\s+balance|available\s+balance|ledger\s+balance|total\s+balance|balance|bal|available|ledger|lien|total)\s*[:\-\.]?\s*(?:rs\.?|inr|₹)?\s*([\d,]+\.\d{2})", re.IGNORECASE)
_RE_CUST_ID = re.compile(r"(?:customer id|cust id|cif|crn)\s*[:\-\.]?\s*([A-Z0-9]{5,15})", re.IGNORECASE)
_RE_UPI_REF = re.compile(r"(?:upi|neft|rtgs|imps)/(?:[a-zA-Z]+)/(\d{10,20})", re.IGNORECASE)
_RE_REF_NO = re.compile(r"(?:txn id|ref no|reference|utr)\s*[:\-\.]?\s*([A-Z0-9]{8,20})", re.IGNORECASE)
_RE_DATE = re.compile(
    r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}"
    r"|\d{1,2}[\-/\.](?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\-/\.]\d{2,4}",
    re.IGNORECASE,
)


def _is_plausible_customer_id(value: str) -> bool:
    cleaned = re.sub(r"[^A-Z0-9]", "", value.upper())
    return 5 <= len(cleaned) <= 15 and cleaned.isalnum() and any(char.isdigit() for char in cleaned)

def extract_contextual_entities(
    ocr_blocks: List[Dict[str, Any]],
    full_text: str,
    document_type: str,
    structure: Optional[Dict[str, Any]] = None,
) -> List[RawMatch]:
    """
    Extract entities using context-aware rules.
    """
    matches = []
    layout_matches: List[RawMatch] = []
    if structure:
        layout_matches = extract_layout_entities(ocr_blocks, structure, document_type)
        matches.extend(layout_matches)
    layout_types = {match.pii_type for match in layout_matches}
    
    # 1. Account Balance
    if "ACCOUNT_BALANCE" not in layout_types:
        for m in _RE_BALANCE.finditer(full_text):
            val = m.group(1).strip()
            # Remove comma for consistent numeric value and clean Rupee artifact (often misread as a repeated first digit like 3, 7, 2)
            clean_val = val.replace(",", "")
            if len(clean_val) >= 2 and clean_val[0] in "237" and clean_val[0] == clean_val[1]:
                clean_val = clean_val[1:]
                val = clean_val  # use the cleaned value for the output

            matches.append(RawMatch(
                pii_type="ACCOUNT_BALANCE",
                value=val,
                start=m.start(1),
                end=m.end(1),
                confidence=0.85,
                reason="Detected near balance keywords (e.g. 'Available Balance')",
                source_rule="Context",
                document_type=document_type
            ))
        
    # 2. Customer ID
    if "CUSTOMER_ID" not in layout_types:
        for m in _RE_CUST_ID.finditer(full_text):
            val = m.group(1).strip()
            if not _is_plausible_customer_id(val):
                logger.info("Rejected contextual Customer ID candidate '%s': validation failed", val)
                continue
            matches.append(RawMatch(
                pii_type="CUSTOMER_ID",
                value=val,
                start=m.start(1),
                end=m.end(1),
                confidence=0.82,
                reason="Detected near Customer ID/CIF labels and validated as an identifier",
                source_rule="Context",
                document_type=document_type,
                context={"validation_checks": ["customer id contains digits and valid length"]}
            ))

    # 3. Transaction Reference (UPI / UTR patterns)
    if structure:
        matches.extend(detect_transaction_context(structure, document_type))

    for m in _RE_UPI_REF.finditer(full_text):
        val = m.group(1).strip()
        matches.append(RawMatch(
            pii_type="TRANSACTION_REFERENCE",
            value=val,
            start=m.start(1),
            end=m.end(1),
            confidence=0.95,
            reason="Detected inside UPI/Bank transaction structure",
            source_rule="Pattern",
            document_type=document_type,
            context={"context_keywords": ["upi"], "transaction_context": True}
        ))

    for m in _RE_REF_NO.finditer(full_text):
        val = m.group(1).strip()
        matches.append(RawMatch(
            pii_type="TRANSACTION_REFERENCE",
            value=val,
            start=m.start(1),
            end=m.end(1),
            confidence=0.88,
            reason="Detected near Txn ID/Ref No labels",
            source_rule="Context",
            document_type=document_type,
            context={"context_keywords": ["txn/ref/utr"], "transaction_context": True}
        ))

    # 4. Transaction History (Pattern Recognition)
    # Detect if we have multiple lines starting with dates, containing numbers
    # A simple heuristic: Count lines with dates
    lines = full_text.split('\n')
    date_line_count = sum(1 for line in lines if _RE_DATE.search(line) and any(char.isdigit() for char in line))
    
    if date_line_count >= 3 and document_type in ["Bank Statement", "Passbook Screen", "Transaction Receipt"]:
        # We classify the whole region or just add a general entity
        matches.append(RawMatch(
            pii_type="TRANSACTION_HISTORY",
            value=f"{date_line_count} transaction rows detected",
            start=0,
            end=len(full_text),
            confidence=0.85,
            reason="Detected repeated date/amount tabular structure",
            source_rule="Pattern",
            document_type=document_type
        ))

    # 5. Account Holder Name Candidates (Heuristic)
    # Names on statements/cards are typically ALL CAPS.
    # We add a strict stop-word list for common banking UI elements to avoid false positives.
    stop_words = {
        "AVAILABLE BALANCE", "ACCOUNT NUMBER", "TRANSACTION HISTORY", "CREDIT CARD", 
        "DEBIT CARD", "SOUTH INDIAN BANK", "SAVINGS GENERAL", "BLOCK CARD", 
        "MANAGE CARD", "SET PIN", "RESET PIN", "CVV", "EXPIRES ON", "RUPAY", "VISA", "MASTERCARD",
        "APPLY NEW CARD", "APPLY NOW", "PAY NOW", "SEND MONEY", "REQUEST MONEY", "ADD PAYEE",
        "VIEW STATEMENT", "DOWNLOAD PDF", "SHARE RECEIPT", "CONFIRM PAYMENT", "PROCEED TO PAY",
        "CLICK HERE", "KNOW MORE", "LEARN MORE", "ADD BENEFICIARY", "NEW CARD", "GET CARD", "NFC"
    }
    forbidden_tokens = {"NFC", "VISA", "MASTERCARD", "RUPAY", "CARD", "CVV", "EXPIRES", "BANK", "SAVINGS", "GENERAL", "BALANCE"}
    current_idx = 0
    for line in lines:
        line_clean = line.strip()
        # Use re.finditer to find ALL CAPS names even if the line has prefixes like "To :" or "From :"
        for m in re.finditer(r"\b[A-Z][A-Z .'-]*(?:\s+[A-Z][A-Z .'-]*){1,4}\b", line_clean):
            name_candidate = m.group(0).strip()
            # Must not contain numbers, and ignore if it's in the stop words or contains forbidden tokens
            tokens = set(name_candidate.split())
            clean_val = name_candidate.replace(" ", "").replace(".", "").replace("-", "").upper()
            is_masking = not clean_val or set(clean_val).issubset({"X", "*"})
            if (not re.search(r"\d", name_candidate) 
                and not is_masking
                and len(name_candidate.split()) >= 2 
                and name_candidate not in stop_words
                and not (tokens & forbidden_tokens)):
                matches.append(RawMatch(
                    pii_type="ACCOUNT_HOLDER_NAME",
                    value=name_candidate,
                    start=current_idx + m.start(),
                    end=current_idx + m.end(),
                    confidence=0.30,  # Weak confidence; AI/Layout must confirm
                    reason="Line segment matches ALL CAPS name heuristics.",
                    source_rule="Context",
                    document_type=document_type
                ))
        current_idx += len(line) + 1

    # 6. Standalone Financial Amounts (Transaction Amounts)
    # Find standalone Rupee values (e.g. "₹ 220", "Rs. 3,000")
    for m in re.finditer(r"(?:rs\.?|inr|\u20b9)\s*([0-9][0-9,]*\.\d{2}|[0-9][0-9,]*)", full_text, re.IGNORECASE):
        val = m.group(0).strip()
        if len(val) > 1 and len(m.group(1)) > 0:
            matches.append(RawMatch(
                pii_type="TRANSACTION_AMOUNT",
                value=val,
                start=m.start(),
                end=m.end(),
                confidence=0.75,
                reason="Detected standalone financial transaction amount",
                source_rule="Context",
                document_type=document_type
            ))

    return matches
