"""
banking_context.py - transaction-first parsing for banking OCR text.
"""

import logging
import re
from typing import Any, Dict, List

from pii_patterns import RawMatch

logger = logging.getLogger(__name__)

TRANSACTION_KEYWORDS = {
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
    "narration",
}

_BANK_CODES = r"(?:SIBL|YESB|SBIN|UBIN|HDFC|ICIC|UTIB|CNRB|PUNB|BARB|KKBK|IDIB|IOBA|FDRL|BKID|MAHB|INDB|PYTM)"
_UPI_CHAIN = re.compile(rf"\b(?:UPI|IMPS|NEFT|RTGS)[/\-\s]+{_BANK_CODES}?[/\-\s]*([A-Z0-9]{{8,22}})\b", re.IGNORECASE)
_LABELED_REF = re.compile(r"\b(?:txn(?:\s*id)?|transaction\s*id|ref(?:erence)?(?:\s*no)?|utr|rrn)\s*[:#/\-\s]+([A-Z0-9]{8,24})\b", re.IGNORECASE)
_DATE_AMOUNT_ROW = re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b.*\b(?:debit|credit|dr|cr|upi|neft|imps|rtgs|transfer|payment)\b", re.IGNORECASE)
_LONG_NUMERIC = re.compile(r"(?<!\d)(\d{10,20})(?!\d)")


def transaction_keyword_hits(text: str) -> List[str]:
    lower_text = (text or "").lower()
    return sorted(keyword for keyword in TRANSACTION_KEYWORDS if keyword in lower_text)


def has_transaction_context(text: str) -> bool:
    return bool(transaction_keyword_hits(text))


def _candidate_reason(value: str, hits: List[str], row_text: str) -> str:
    safe_row = row_text.strip()
    if len(safe_row) > 160:
        safe_row = safe_row[:157] + "..."
    return (
        f"Detected banking transaction reference '{value}' with context "
        f"keywords [{', '.join(hits)}] in OCR row: {safe_row}"
    )


def detect_transaction_context(structure: Dict[str, Any], document_type: str) -> List[RawMatch]:
    matches: List[RawMatch] = []
    seen = set()
    lines = structure.get("lines", [])
    full_text = structure.get("full_text", "")

    for line in lines:
        line_text = line.get("text", "")
        context_text = line.get("context_text", line_text)
        hits = transaction_keyword_hits(context_text)
        row_like = bool(_DATE_AMOUNT_ROW.search(context_text))

        candidate_iterators = [
            ("TransactionContext:UPIChain", _UPI_CHAIN.finditer(line_text)),
            ("TransactionContext:LabeledRef", _LABELED_REF.finditer(line_text)),
        ]

        if hits or row_like:
            candidate_iterators.append(("TransactionContext:BankingRowNumber", _LONG_NUMERIC.finditer(line_text)))

        for source_rule, iterator in candidate_iterators:
            for match in iterator:
                value = match.group(1).strip()
                if not value or len(value) < 8:
                    continue
                start = line.get("start", 0) + match.start(1)
                end = line.get("start", 0) + match.end(1)
                key = (value.lower(), start, end)
                if key in seen:
                    continue
                seen.add(key)

                local_hits = hits or transaction_keyword_hits(line_text)
                confidence = 0.96 if source_rule.endswith("UPIChain") else 0.91
                if row_like:
                    confidence = max(confidence, 0.90)
                    local_hits = sorted(set(local_hits + ["transaction row"]))

                logger.info(
                    "Transaction context match: value=%s rule=%s keywords=%s confidence=%.2f",
                    value,
                    source_rule,
                    local_hits,
                    confidence,
                )
                matches.append(RawMatch(
                    pii_type="TRANSACTION_REFERENCE",
                    value=value,
                    start=start,
                    end=end,
                    confidence=confidence,
                    reason=_candidate_reason(value, local_hits, line_text),
                    source_rule=source_rule,
                    document_type=document_type,
                    context={
                        "line_text": line_text,
                        "context_keywords": local_hits,
                        "line_index": line.get("line_index"),
                        "transaction_context": True,
                    },
                ))

    logger.info(
        "Transaction context detector complete: %s matches over %s OCR lines, text_chars=%s",
        len(matches),
        len(lines),
        len(full_text),
    )
    return matches
