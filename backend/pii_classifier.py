"""
pii_classifier.py — Layer 2: Classification + Bounding Box Mapping
====================================================================
Maps raw regex matches onto PII categories, risk levels, and links them
to the OCR bounding boxes that produced the text.
"""

import logging
from typing import List, Dict, Any, Optional
from pii_patterns import RawMatch, detect_all
from document_classifier import classify_document
from pii_context import extract_contextual_entities
from aadhaar_validator import validate_aadhaar_candidate
from banking_context import has_transaction_context, transaction_keyword_hits
from ocr_structure import line_context_for_span, parse_ocr_structure

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Category & Risk catalogue
# ─────────────────────────────────────────────────────────────────────────────

_CATEGORY_MAP: Dict[str, str] = {
    "PAN":                  "KYC Documents",
    "AADHAAR_UNMASKED":     "KYC Documents",
    "AADHAAR_MASKED":       "KYC Documents",
    "PASSPORT":             "KYC Documents",
    "VOTER_ID":             "KYC Documents",
    "DRIVING_LICENCE":      "KYC Documents",
    "EMAIL":                "Identity Data",
    "PHONE_IN":             "Identity Data",
    "DATE_OF_BIRTH":        "Identity Data",
    "_KW_PHOTOGRAPH":       "Identity Data",
    "_KW_SIGNATURE":        "Identity Data",
    "CREDIT_DEBIT_CARD":    "Financial Data",
    "MASKED_CARD":          "Financial Data",
    "BANK_ACCOUNT":         "Financial Data",
    "IFSC":                 "Financial Data",
    "UPI_HANDLE":           "Financial Data",
    "IP_ADDRESS":           "Online Identifiers",
    "_KW_PASSWORD":         "Online Identifiers",
    "_KW_COOKIE":           "Online Identifiers",
    "_KW_CCTV":             "Other Information",
    "_KW_VOICE":            "Other Information",
    "ACCOUNT_BALANCE":      "Financial Data",
    "CUSTOMER_ID":          "Identity Data",
    "ACCOUNT_HOLDER_NAME":  "Identity Data",
    "BRANCH_NAME":          "Financial Data",
    "TRANSACTION_REFERENCE": "Financial Data",
    "TRANSACTION_HISTORY":  "Financial Data",
}

_RISK_MAP: Dict[str, str] = {
    "PAN":                  "High",
    "AADHAAR_UNMASKED":     "Critical",   # fully exposed government ID
    "AADHAAR_MASKED":       "Medium",
    "PASSPORT":             "High",
    "VOTER_ID":             "Medium",
    "DRIVING_LICENCE":      "Medium",
    "EMAIL":                "Medium",
    "PHONE_IN":             "High",
    "DATE_OF_BIRTH":        "Medium",
    "_KW_PHOTOGRAPH":       "Low",
    "_KW_SIGNATURE":        "Low",
    "CREDIT_DEBIT_CARD":    "Critical",   # full card number — fraud risk
    "MASKED_CARD":          "Medium",
    "BANK_ACCOUNT":         "High",
    "IFSC":                 "High",
    "UPI_HANDLE":           "High",
    "IP_ADDRESS":           "Medium",
    "_KW_PASSWORD":         "Critical",
    "_KW_COOKIE":           "Medium",
    "_KW_CCTV":             "Low",
    "_KW_VOICE":            "Low",
    "ACCOUNT_BALANCE":      "High",
    "CUSTOMER_ID":          "High",
    "ACCOUNT_HOLDER_NAME":  "High",
    "BRANCH_NAME":          "High",
    "TRANSACTION_REFERENCE": "None",
    "TRANSACTION_HISTORY":  "High",
}

# Friendly display names (strip internal prefixes)
_DISPLAY_NAME: Dict[str, str] = {
    "PAN":                  "PAN Details",
    "AADHAAR_UNMASKED":     "Aadhaar Details (Unmasked)",
    "AADHAAR_MASKED":       "Aadhaar Details (Masked)",
    "PASSPORT":             "Passport Number",
    "VOTER_ID":             "Voter ID",
    "DRIVING_LICENCE":      "Driving Licence",
    "EMAIL":                "Personal Email ID",
    "PHONE_IN":             "Personal Phone Number",
    "DATE_OF_BIRTH":        "Date of Birth",
    "_KW_PHOTOGRAPH":       "Photograph Reference",
    "_KW_SIGNATURE":        "Signature Reference",
    "CREDIT_DEBIT_CARD":    "Credit/Debit Card Details",
    "MASKED_CARD":          "Masked Card Number",
    "BANK_ACCOUNT":         "Bank Account Number",
    "IFSC":                 "IFSC Code",
    "UPI_HANDLE":           "UPI Handle",
    "IP_ADDRESS":           "IP Address",
    "_KW_PASSWORD":         "Password Reference",
    "_KW_COOKIE":           "Cookie / Session Reference",
    "_KW_CCTV":             "CCTV / Surveillance Reference",
    "_KW_VOICE":            "Voice Recording Reference",
    "ACCOUNT_BALANCE":      "Account Balance",
    "CUSTOMER_ID":          "Customer ID",
    "ACCOUNT_HOLDER_NAME":  "Account Holder Name",
    "BRANCH_NAME":          "Branch Name",
    "TRANSACTION_REFERENCE": "Transaction Reference",
    "TRANSACTION_HISTORY":  "Transaction History",
}


# ─────────────────────────────────────────────────────────────────────────────
# Block structure expected from OCR layer
# ─────────────────────────────────────────────────────────────────────────────

# Each OCR block: {"text": str, "confidence": float, "bbox": [[x,y], ...]}

def _build_full_text(ocr_blocks: List[Dict[str, Any]]) -> str:
    """Join block texts with newlines for full-document matching."""
    return parse_ocr_structure(ocr_blocks).get("full_text", "")


def _map_match_to_block(
    raw_match: RawMatch,
    ocr_blocks: List[Dict[str, Any]],
    full_text: str,
) -> tuple[List[int], Optional[List]]:
    """
    Find which OCR block(s) contain the matched PII value.
    Returns (list_of_block_indices, primary_bbox).
    """
    value = raw_match.value.strip()
    matched_indices = []
    primary_bbox = None

    for idx, block in enumerate(ocr_blocks):
        block_text = block.get("text", "")
        if value.lower() in block_text.lower() or block_text.strip().lower() in value.lower():
            matched_indices.append(idx)
            if primary_bbox is None:
                primary_bbox = block.get("bbox")

    if not matched_indices:
        # Fallback: try substring containment with any word from the value
        words = [w for w in value.split() if len(w) >= 4]
        for idx, block in enumerate(ocr_blocks):
            block_text = block.get("text", "")
            if any(w.lower() in block_text.lower() for w in words):
                matched_indices.append(idx)
                if primary_bbox is None:
                    primary_bbox = block.get("bbox")

    return matched_indices, primary_bbox


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _spans_overlap(a: RawMatch, b: RawMatch) -> bool:
    return a.start < b.end and a.end > b.start


def _safe_log_value(value: str) -> str:
    text = str(value or "")
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}***{text[-2:]}"


def _account_context_hits(text: str) -> List[str]:
    lower_text = (text or "").lower()
    keywords = ["account", "acct", "a/c", "account no", "account number", "sb ", "savings", "current"]
    return [keyword for keyword in keywords if keyword in lower_text]


def _context_for_match(raw_match: RawMatch, structure: Dict[str, Any]) -> Dict[str, Any]:
    context = line_context_for_span(structure, raw_match.start, raw_match.end)
    merged = dict(raw_match.context or {})
    merged.setdefault("line_indices", context.get("line_indices", []))
    merged.setdefault("ocr_context", context.get("context_text", ""))
    merged.setdefault("context_keywords", transaction_keyword_hits(context.get("context_text", "")))
    if context.get("bbox"):
        merged.setdefault("line_bbox", context.get("bbox"))
    if context.get("block_indices"):
        merged.setdefault("context_block_indices", context.get("block_indices"))
    return merged


def _apply_priority_rules(
    regex_matches: List[RawMatch],
    context_matches: List[RawMatch],
    structure: Dict[str, Any],
    doc_type: str,
) -> List[RawMatch]:
    transaction_matches = [
        match for match in context_matches
        if match.pii_type == "TRANSACTION_REFERENCE"
    ]
    accepted: List[RawMatch] = []

    for match in regex_matches:
        if not match.document_type:
            match.document_type = doc_type
        match.context = _context_for_match(match, structure)
        context_text = match.context.get("ocr_context", "")
        overlapping_transaction = next(
            (txn for txn in transaction_matches if _spans_overlap(match, txn)),
            None,
        )

        logger.info(
            "Classifying regex match type=%s value=%s rule=%s context_keywords=%s",
            match.pii_type,
            _safe_log_value(match.value),
            match.source_rule,
            match.context.get("context_keywords", []),
        )

        if match.pii_type == "AADHAAR_UNMASKED":
            validation = validate_aadhaar_candidate(match.value, context_text)
            match.context["aadhaar_validation"] = validation
            logger.info(
                "Aadhaar candidate value=%s checksum=%s format=%s banking_context=%s confidence=%.2f reason=%s",
                _safe_log_value(match.value),
                validation["checksum_valid"],
                validation["format_valid"],
                validation["banking_context"],
                validation["confidence"],
                validation["reason"],
            )

            if overlapping_transaction:
                logger.info(
                    "Rejected Aadhaar candidate value=%s: transaction reference overlap value=%s",
                    _safe_log_value(match.value),
                    _safe_log_value(overlapping_transaction.value),
                )
                continue

            if has_transaction_context(context_text) and not validation["context_supported"]:
                logger.info(
                    "Rejected Aadhaar candidate value=%s: banking row context without Aadhaar label",
                    _safe_log_value(match.value),
                )
                continue

            if not validation["is_valid"] or validation["confidence"] < 0.75:
                logger.info(
                    "Rejected Aadhaar candidate value=%s: checksum/context confidence insufficient",
                    _safe_log_value(match.value),
                )
                continue

            match.confidence = validation["confidence"]
            match.reason = (
                "Validated Aadhaar candidate: "
                f"checksum_valid={validation['checksum_valid']}; "
                f"context_supported={validation['context_supported']}; "
                f"{validation['reason']}"
            )
            match.source_rule = "Regex+AadhaarValidation"
            accepted.append(match)
            continue

        if match.pii_type == "AADHAAR_MASKED":
            lower_context = context_text.lower()
            if overlapping_transaction or (
                has_transaction_context(context_text)
                and "aadhaar" not in lower_context
                and "aadhar" not in lower_context
            ):
                logger.info(
                    "Rejected masked Aadhaar candidate value=%s: banking transaction context",
                    _safe_log_value(match.value),
                )
                continue
            match.context["aadhaar_validation"] = {
                "masked": True,
                "checksum_valid": None,
                "context_keywords": match.context.get("context_keywords", []),
            }
            accepted.append(match)
            continue

        if match.pii_type == "BANK_ACCOUNT":
            overlapping_aadhaar = next(
                (item for item in accepted if item.pii_type in {"AADHAAR_UNMASKED", "AADHAAR_MASKED"} and _spans_overlap(match, item)),
                None,
            )
            account_hits = _account_context_hits(context_text)
            if overlapping_transaction:
                logger.info(
                    "Rejected bank account candidate value=%s: transaction reference takes priority",
                    _safe_log_value(match.value),
                )
                continue
            if overlapping_aadhaar:
                logger.info(
                    "Rejected bank account candidate value=%s: validated Aadhaar takes priority",
                    _safe_log_value(match.value),
                )
                continue
            if not account_hits and len(match.value) == 12:
                match.confidence = min(match.confidence, 0.35)
                logger.info(
                    "Rejected ambiguous 12 digit account candidate value=%s: no account label/context",
                    _safe_log_value(match.value),
                )
                continue
            if account_hits:
                match.confidence = min(0.90, match.confidence + 0.12)
                match.reason = (
                    f"Detected numeric bank account candidate with account context: {', '.join(account_hits)}"
                )
                match.context["account_context_keywords"] = account_hits

        accepted.append(match)

    layout_matches = [
        match for match in context_matches
        if (match.context or {}).get("layout_mapping")
    ]
    other_context_matches = [
        match for match in context_matches
        if not (match.context or {}).get("layout_mapping")
    ]
    final_matches = layout_matches + accepted + other_context_matches
    deduped: List[RawMatch] = []
    seen = set()
    for match in final_matches:
        key = (match.pii_type, match.value.replace(" ", "").replace("-", "").lower(), match.start, match.end)
        if key in seen:
            continue
        seen.add(key)
        if not match.document_type:
            match.document_type = doc_type
        if not match.context:
            match.context = _context_for_match(match, structure)
        deduped.append(match)
    return deduped


def detect_pii_in_blocks(ocr_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Main entry point for Layer 2.

    Args:
        ocr_blocks: list of OCR block dicts from OCR engine
                    Each: {"text": str, "confidence": float, "bbox": [[x,y],...]}

    Returns:
        List of classified PII entity dicts ready for API response.
    """
    structure = parse_ocr_structure(ocr_blocks)
    full_text = structure.get("full_text", "")
    logger.info(f"Running PII detection on {len(ocr_blocks)} OCR blocks, "
                f"{len(full_text)} chars total, {len(structure.get('lines', []))} OCR lines.")

    doc_type = classify_document(ocr_blocks, full_text)
    logger.info(f"Document classified as: {doc_type}")

    regex_matches: List[RawMatch] = detect_all(full_text)
    context_matches: List[RawMatch] = extract_contextual_entities(
        ocr_blocks,
        full_text,
        doc_type,
        structure=structure,
    )
    all_raw_matches = _apply_priority_rules(regex_matches, context_matches, structure, doc_type)
    logger.info(f"Raw regex matches: {len(regex_matches)}, Context matches: {len(context_matches)}, Final: {len(all_raw_matches)}")

    entities: List[Dict[str, Any]] = []
    seen_values: set = set()   # deduplicate by (type, normalised_value)

    for raw in all_raw_matches:
        dedup_key = (raw.pii_type, raw.value.replace(" ", "").replace("-", "").lower())
        if dedup_key in seen_values:
            logger.debug(f"Skipping duplicate: {dedup_key}")
            continue
        seen_values.add(dedup_key)

        line_context = line_context_for_span(structure, raw.start, raw.end)
        raw_context = raw.context or {}
        block_indices = raw_context.get("value_block_indices") or line_context.get("block_indices") or []
        bbox = raw_context.get("value_bbox") or line_context.get("bbox")
        if not block_indices:
            block_indices, bbox = _map_match_to_block(raw, ocr_blocks, full_text)

        validation = raw_context.get("aadhaar_validation", {})
        ocr_line_indices = raw_context.get("line_indices") or line_context.get("line_indices", [])
        ocr_context = raw_context.get("ocr_context") or line_context.get("context_text", "")

        entity = {
            "type":             _DISPLAY_NAME.get(raw.pii_type, raw.pii_type),
            "classification":   _DISPLAY_NAME.get(raw.pii_type, raw.pii_type),
            "raw_type":         raw.pii_type,
            "value":            raw.value,
            "category":         _CATEGORY_MAP.get(raw.pii_type, "Other Information"),
            "confidence":       round(raw.confidence, 4),
            "masked":           raw.masked,
            "risk":             _RISK_MAP.get(raw.pii_type, "Low"),
            "ocr_block_indices": block_indices,
            "ocr_line_indices":  ocr_line_indices,
            "ocr_context":       ocr_context,
            "bbox":             bbox,
            "reason":           raw.reason,
            "source_rule":      raw.source_rule,
            "document_type":    raw.document_type,
            "validation_status": validation or raw.context or {},
            "aadhaar_checksum_valid": validation.get("checksum_valid") if validation else None,
            "contextual_reasoning": raw.reason,
        }
        for field in (
            "label",
            "mapping_reason",
            "extraction_confidence",
            "spatial_confidence",
            "validation_confidence",
            "label_block_indices",
            "value_block_indices",
            "layout_relation",
        ):
            if field in raw_context:
                entity[field] = raw_context[field]
        entities.append(entity)
        logger.info(
            f"  [{entity['risk']:8}] {entity['type']:<40} | "
            f"conf={entity['confidence']:.2f} | masked={entity['masked']} | "
            f"blocks={block_indices}"
        )

    logger.info(f"PII classification complete: {len(entities)} unique entities.")
    return entities
