"""
entity_resolution.py - final hybrid entity classification.

This stage fuses deterministic candidate evidence with AI semantic resolution.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from entity_catalog import CATEGORY_MAP, DISPLAY_NAME, RISK_MAP

logger = logging.getLogger(__name__)

AI_TYPE_ALIASES = {
    "AADHAAR": "AADHAAR_UNMASKED",
    "AADHAAR_NUMBER": "AADHAAR_UNMASKED",
    "BANK_ACCOUNT_NUMBER": "BANK_ACCOUNT",
    "ACCOUNT_NUMBER": "BANK_ACCOUNT",
    "IFSC_CODE": "IFSC",
    "CUSTOMERID": "CUSTOMER_ID",
    "CUSTOMER_ID": "CUSTOMER_ID",
    "NAME": "ACCOUNT_HOLDER_NAME",
    "ACCOUNT_HOLDER_NAME": "ACCOUNT_HOLDER_NAME",
    "BRANCH": "BRANCH_NAME",
    "BRANCH_NAME": "BRANCH_NAME",
    "TRANSACTION_ID": "TRANSACTION_REFERENCE",
    "TRANSACTION_REFERENCE": "TRANSACTION_REFERENCE",
    "TRANSACTION_HISTORY": "TRANSACTION_HISTORY",
    "ACCOUNT_BALANCE": "ACCOUNT_BALANCE",
}


def _normalise_type(entity_type: str) -> str:
    key = re.sub(r"[^A-Z0-9_]+", "_", str(entity_type or "").upper()).strip("_")
    return AI_TYPE_ALIASES.get(key, key)


def _normalise_value(value: str) -> str:
    return re.sub(r"[\s,\-]+", "", str(value or "")).lower()


def _ai_decisions_by_value(ai_resolution: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    decisions = {}
    for item in ai_resolution.get("entity_classifications", []) or []:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        if not value:
            continue
        entity_type = _normalise_type(item.get("final_type") or item.get("entity_type"))
        if not entity_type or entity_type in {"IGNORE", "NOT_PII", "UNKNOWN"}:
            continue
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        decisions[_normalise_value(value)] = {
            "value": value,
            "final_type": entity_type,
            "confidence": round(confidence, 4),
            "reasoning": str(item.get("reasoning", "")),
            "supporting_evidence": item.get("supporting_evidence", []),
            "rejected_candidates": item.get("rejected_candidates", []),
        }
    return decisions


def _best_deterministic_evidence(candidate: Dict[str, Any]) -> Dict[str, Any]:
    evidence = candidate.get("evidence") or []
    if not evidence:
        return {}
    return max(evidence, key=lambda item: item.get("confidence", 0))


def _evidence_for_type(candidate: Dict[str, Any], entity_type: str) -> Optional[Dict[str, Any]]:
    matches = [
        item for item in candidate.get("evidence", [])
        if item.get("candidate_type") == entity_type
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: item.get("confidence", 0))


def _fused_confidence(
    *,
    ai_confidence: float,
    deterministic_confidence: float,
    ocr_confidence: float,
    layout_confidence: float,
) -> float:
    weights = {
        "ai": 0.45 if ai_confidence > 0 else 0.0,
        "deterministic": 0.25,
        "ocr": 0.15,
        "layout": 0.15 if layout_confidence > 0 else 0.0,
    }
    total = sum(weights.values()) or 1.0
    score = (
        ai_confidence * weights["ai"]
        + deterministic_confidence * weights["deterministic"]
        + ocr_confidence * weights["ocr"]
        + layout_confidence * weights["layout"]
    ) / total
    return round(max(0.0, min(0.99, score)), 4)


def _should_keep(candidate: Dict[str, Any], final_type: str, confidence: float, ai_decision: Optional[Dict[str, Any]]) -> bool:
    if final_type in {"IGNORE", "NOT_PII", "UNKNOWN"}:
        return False
    if final_type in {"TRANSACTION_REFERENCE"}:
        return confidence >= 0.45
    if ai_decision:
        return confidence >= 0.35
    return confidence >= 0.50


def resolve_entities(
    candidate_payload: Dict[str, Any],
    ai_resolution: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    ai_resolution = ai_resolution or {}
    ai_by_value = _ai_decisions_by_value(ai_resolution)
    final_entities: List[Dict[str, Any]] = []
    seen = set()

    for candidate in candidate_payload.get("candidates", []):
        key = _normalise_value(candidate.get("value", ""))
        ai_decision = ai_by_value.get(key)

        deterministic = _best_deterministic_evidence(candidate)
        final_type = deterministic.get("candidate_type")
        ai_confidence = 0.0
        if ai_decision:
            final_type = ai_decision["final_type"]
            ai_confidence = ai_decision.get("confidence", 0.0)

        typed_evidence = _evidence_for_type(candidate, final_type) or deterministic
        deterministic_confidence = typed_evidence.get("confidence", candidate.get("best_deterministic_confidence", 0.0))
        ocr_confidence = typed_evidence.get("ocr_confidence", candidate.get("ocr_confidence", 0.0))
        layout_confidence = 0.0
        validation = typed_evidence.get("validation", {}) or {}
        if validation.get("layout_mapping"):
            layout_confidence = max(
                float(validation.get("spatial_confidence") or 0),
                float(validation.get("validation_confidence") or 0),
            )

        confidence = _fused_confidence(
            ai_confidence=ai_confidence,
            deterministic_confidence=deterministic_confidence,
            ocr_confidence=ocr_confidence,
            layout_confidence=layout_confidence,
        )
        if not final_type or not _should_keep(candidate, final_type, confidence, ai_decision):
            logger.info(
                "Dropped candidate value=%s final_type=%s confidence=%.2f ai=%s",
                candidate.get("value"),
                final_type,
                confidence,
                bool(ai_decision),
            )
            continue

        dedupe_key = (final_type, key)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        validation_status = {
            "candidate_types": candidate.get("candidate_types", []),
            "selected_evidence": typed_evidence,
            "ai_resolution": ai_decision,
            "fusion": {
                "ai_confidence": ai_confidence,
                "deterministic_confidence": deterministic_confidence,
                "ocr_confidence": ocr_confidence,
                "layout_confidence": layout_confidence,
                "final_confidence": confidence,
            },
        }
        value = candidate.get("value")
        if ai_decision and ai_decision.get("value"):
            value = ai_decision["value"]

        reason = (
            ai_decision.get("reasoning")
            if ai_decision
            else typed_evidence.get("reason") or "Selected from highest-confidence deterministic candidate evidence."
        )
        entity = {
            "type": DISPLAY_NAME.get(final_type, final_type),
            "classification": DISPLAY_NAME.get(final_type, final_type),
            "raw_type": final_type,
            "value": value,
            "category": CATEGORY_MAP.get(final_type, "Other Information"),
            "confidence": confidence,
            "masked": final_type in {"AADHAAR_MASKED", "MASKED_CARD"},
            "risk": RISK_MAP.get(final_type, "Low"),
            "ocr_block_indices": typed_evidence.get("ocr_block_indices", candidate.get("ocr_block_indices", [])),
            "ocr_line_indices": typed_evidence.get("ocr_line_indices", candidate.get("ocr_line_indices", [])),
            "ocr_context": typed_evidence.get("ocr_context", candidate.get("ocr_context", "")),
            "bbox": typed_evidence.get("bbox", candidate.get("bbox")),
            "reason": reason,
            "source_rule": "HybridAIResolution" if ai_decision else "CandidateResolutionFallback",
            "document_type": candidate_payload.get("document_type") or candidate.get("document_type"),
            "validation_status": validation_status,
            "aadhaar_checksum_valid": (
                validation.get("aadhaar_validation", {}).get("checksum_valid")
                if isinstance(validation.get("aadhaar_validation"), dict)
                else None
            ),
            "contextual_reasoning": reason,
            "source_evidence": candidate.get("candidate_types", []),
            "rejected_candidates": ai_decision.get("rejected_candidates", []) if ai_decision else [],
        }
        for field in ("label", "layout_relation", "label_block_indices", "value_block_indices"):
            if typed_evidence.get(field) is not None:
                entity[field] = typed_evidence[field]
        final_entities.append(entity)

    logger.info(
        "Entity resolution complete: candidates=%s ai_decisions=%s final=%s",
        len(candidate_payload.get("candidates", [])),
        len(ai_by_value),
        len(final_entities),
    )
    return final_entities
