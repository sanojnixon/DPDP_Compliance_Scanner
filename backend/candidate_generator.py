"""
candidate_generator.py - deterministic evidence generation for hybrid PII.

Regex, validators, transaction context, and layout mapping produce candidate
types. They do not decide the final entity classification.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from aadhaar_validator import validate_aadhaar_candidate
from banking_context import has_transaction_context, transaction_keyword_hits
from document_classifier import classify_document
from layout_mapping import build_layout_debug
from ocr_structure import line_context_for_span, parse_ocr_structure
from pii_context import extract_contextual_entities
from pii_patterns import RawMatch, detect_all

logger = logging.getLogger(__name__)


def _normalise_value(value: str) -> str:
    return re.sub(r"[\s,\-]+", "", str(value or "")).lower()


def _bbox_bounds(bbox: Optional[List[List[float]]]) -> Tuple[float, float, float, float]:
    if not bbox:
        return 0.0, 0.0, 0.0, 0.0
    xs = [float(point[0]) for point in bbox]
    ys = [float(point[1]) for point in bbox]
    return min(xs), min(ys), max(xs), max(ys)


def _merge_bboxes(bboxes: List[List[List[float]]]) -> Optional[List[List[float]]]:
    bounds = [_bbox_bounds(bbox) for bbox in bboxes if bbox]
    if not bounds:
        return None
    x1 = min(item[0] for item in bounds)
    y1 = min(item[1] for item in bounds)
    x2 = max(item[2] for item in bounds)
    y2 = max(item[3] for item in bounds)
    return [[round(x1, 1), round(y1, 1)], [round(x2, 1), round(y1, 1)], [round(x2, 1), round(y2, 1)], [round(x1, 1), round(y2, 1)]]


def _find_blocks_for_value(value: str, ocr_blocks: List[Dict[str, Any]]) -> Tuple[List[int], Optional[List[List[float]]], float]:
    value_norm = _normalise_value(value)
    matched = []
    for idx, block in enumerate(ocr_blocks):
        block_norm = _normalise_value(block.get("text", ""))
        if value_norm and (value_norm in block_norm or block_norm in value_norm):
            matched.append(idx)

    if not matched:
        words = [word for word in str(value).split() if len(word) >= 4]
        for idx, block in enumerate(ocr_blocks):
            text = str(block.get("text", "")).lower()
            if any(word.lower() in text for word in words):
                matched.append(idx)

    bboxes = [ocr_blocks[idx].get("bbox") for idx in matched]
    confidences = [float(ocr_blocks[idx].get("confidence", 0) or 0) for idx in matched]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return matched, _merge_bboxes(bboxes), round(avg_conf, 4)


def _candidate_confidence(raw: RawMatch, context_text: str) -> Tuple[float, Dict[str, Any]]:
    metadata: Dict[str, Any] = {
        "source_confidence": raw.confidence,
        "context_keywords": transaction_keyword_hits(context_text),
    }

    confidence = raw.confidence
    if raw.pii_type == "AADHAAR_UNMASKED":
        validation = validate_aadhaar_candidate(raw.value, context_text)
        metadata["aadhaar_validation"] = validation
        confidence = validation.get("confidence", 0.0)
        if has_transaction_context(context_text) and not validation.get("context_supported"):
            confidence = min(confidence, 0.18)
            metadata["semantic_warning"] = "12-digit value appears in banking transaction context"

    if raw.pii_type == "BANK_ACCOUNT" and has_transaction_context(context_text):
        confidence = min(confidence, 0.25)
        metadata["semantic_warning"] = "numeric value appears in transaction context"

    if (raw.context or {}).get("layout_mapping"):
        confidence = max(confidence, raw.confidence)
        metadata.update({
            "layout_mapping": True,
            "label": raw.context.get("label"),
            "mapping_reason": raw.context.get("mapping_reason"),
            "spatial_confidence": raw.context.get("spatial_confidence"),
            "validation_confidence": raw.context.get("validation_confidence"),
            "extraction_confidence": raw.context.get("extraction_confidence"),
            "candidate_rankings": raw.context.get("candidate_rankings", []),
        })

    return round(max(0.0, min(0.99, confidence)), 4), metadata


def _raw_match_to_evidence(
    raw: RawMatch,
    *,
    ocr_blocks: List[Dict[str, Any]],
    structure: Dict[str, Any],
    document_type: str,
) -> Dict[str, Any]:
    context = line_context_for_span(structure, raw.start, raw.end)
    raw_context = raw.context or {}
    context_text = raw_context.get("ocr_context") or context.get("context_text", "")
    block_indices = raw_context.get("value_block_indices") or context.get("block_indices") or []
    bbox = raw_context.get("value_bbox") or context.get("bbox")
    ocr_confidence = 0.0
    if not block_indices:
        block_indices, bbox, ocr_confidence = _find_blocks_for_value(raw.value, ocr_blocks)
    else:
        confs = [float(ocr_blocks[idx].get("confidence", 0) or 0) for idx in block_indices if idx < len(ocr_blocks)]
        ocr_confidence = round(sum(confs) / len(confs), 4) if confs else 0.0

    confidence, validation = _candidate_confidence(raw, context_text)
    return {
        "candidate_type": raw.pii_type,
        "display_type": raw.pii_type,
        "confidence": confidence,
        "source_rule": raw.source_rule,
        "reason": raw.reason,
        "start": raw.start,
        "end": raw.end,
        "document_type": raw.document_type or document_type,
        "ocr_block_indices": block_indices,
        "ocr_line_indices": raw_context.get("line_indices") or context.get("line_indices", []),
        "ocr_context": context_text,
        "bbox": bbox,
        "ocr_confidence": ocr_confidence,
        "validation": validation,
        "label": raw_context.get("label"),
        "layout_relation": raw_context.get("layout_relation"),
        "label_block_indices": raw_context.get("label_block_indices"),
        "value_block_indices": raw_context.get("value_block_indices"),
    }


def _candidate_from_evidence(value: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    best = max(evidence, key=lambda item: item.get("confidence", 0))
    candidate_types = []
    seen = set()
    for item in sorted(evidence, key=lambda ev: ev.get("confidence", 0), reverse=True):
        if item["candidate_type"] in seen:
            continue
        seen.add(item["candidate_type"])
        candidate_types.append({
            "type": item["candidate_type"],
            "confidence": item["confidence"],
            "source_rule": item.get("source_rule"),
            "reason": item.get("reason"),
            "validation": item.get("validation", {}),
        })

    return {
        "value": value,
        "candidate_types": candidate_types,
        "evidence": evidence,
        "best_deterministic_type": best.get("candidate_type"),
        "best_deterministic_confidence": best.get("confidence", 0),
        "ocr_confidence": best.get("ocr_confidence", 0),
        "ocr_block_indices": best.get("ocr_block_indices", []),
        "ocr_line_indices": best.get("ocr_line_indices", []),
        "ocr_context": best.get("ocr_context", ""),
        "bbox": best.get("bbox"),
        "document_type": best.get("document_type"),
    }


def generate_entity_candidates(
    ocr_blocks: List[Dict[str, Any]],
    structure: Optional[Dict[str, Any]] = None,
    document_type: Optional[str] = None,
) -> Dict[str, Any]:
    structure = structure or parse_ocr_structure(ocr_blocks)
    full_text = structure.get("full_text", "")
    document_type = document_type or classify_document(ocr_blocks, full_text)

    regex_matches = detect_all(full_text)
    context_matches = extract_contextual_entities(
        ocr_blocks,
        full_text,
        document_type,
        structure=structure,
    )
    raw_matches = regex_matches + context_matches

    grouped: Dict[str, Dict[str, Any]] = {}
    for raw in raw_matches:
        key = _normalise_value(raw.value)
        if not key:
            continue
        evidence = _raw_match_to_evidence(
            raw,
            ocr_blocks=ocr_blocks,
            structure=structure,
            document_type=document_type,
        )
        if key not in grouped:
            grouped[key] = {"value": raw.value, "evidence": []}
        grouped[key]["evidence"].append(evidence)

    candidates = [
        _candidate_from_evidence(item["value"], item["evidence"])
        for item in grouped.values()
    ]
    candidates.sort(key=lambda item: item.get("best_deterministic_confidence", 0), reverse=True)

    layout_debug = build_layout_debug(ocr_blocks, structure, document_type)
    logger.info(
        "Candidate generation complete: regex=%s context=%s grouped=%s",
        len(regex_matches),
        len(context_matches),
        len(candidates),
    )
    return {
        "document_type": document_type,
        "candidates": candidates,
        "layout_debug": layout_debug,
        "stats": {
            "regex_matches": len(regex_matches),
            "context_matches": len(context_matches),
            "candidate_values": len(candidates),
        },
    }
