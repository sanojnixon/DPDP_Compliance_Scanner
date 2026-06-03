"""
layout_mapping.py - layout-aware label/value extraction for banking screens.

This module keeps OCR engine output deterministic: it uses bounding boxes,
nearby labels, and entity-specific validators before sending candidates to the
PII classifier.
"""

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from banking_context import has_transaction_context
from pii_patterns import RawMatch

logger = logging.getLogger(__name__)


_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"(?:rs\.?|inr|\u20b9)?\s*([0-9][0-9,]*\.\d{2})", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SPACE_RE = re.compile(r"\s+")

_LABEL_ALIASES = {
    "CUSTOMER_ID": {
        "customerid", "custid", "cif", "cifnumber", "crn", "customeridentification",
    },
    "BANK_ACCOUNT": {
        "accountnumber", "accountno", "acctnumber", "acctno", "acnumber", "acno",
    },
    "IFSC": {
        "ifsccode", "ifsc",
    },
    "BRANCH_NAME": {
        "branchname", "branch",
    },
    "ACCOUNT_BALANCE": {
        "accountbalance", "availablebalance", "ledgerbalance", "totalbalance", "balance",
    },
    "ACCOUNT_HOLDER_NAME": {
        "accountholdername", "holdername", "accountname", "customername",
    },
}

_LABEL_BY_ALIAS = {
    alias: entity_type
    for entity_type, aliases in _LABEL_ALIASES.items()
    for alias in aliases
}

_SUMMARY_STOP_LABELS = {"ministatement", "statement", "transactionhistory"}


def _norm_label(text: str) -> str:
    return _NON_ALNUM_RE.sub("", (text or "").lower())


def _clean_spaces(text: str) -> str:
    return _SPACE_RE.sub(" ", str(text or "").strip())


def _bbox_bounds(bbox: Optional[List[List[float]]]) -> Tuple[float, float, float, float]:
    if not bbox:
        return 0.0, 0.0, 0.0, 0.0
    xs = [float(point[0]) for point in bbox]
    ys = [float(point[1]) for point in bbox]
    return min(xs), min(ys), max(xs), max(ys)


def _merge_bounds(records: Iterable[Dict[str, Any]]) -> List[List[float]]:
    bounds = [_bbox_bounds(record.get("bbox")) for record in records]
    if not bounds:
        return []
    x1 = min(item[0] for item in bounds)
    y1 = min(item[1] for item in bounds)
    x2 = max(item[2] for item in bounds)
    y2 = max(item[3] for item in bounds)
    return [[round(x1, 1), round(y1, 1)], [round(x2, 1), round(y1, 1)], [round(x2, 1), round(y2, 1)], [round(x1, 1), round(y2, 1)]]


def _geometry_from_bbox(bbox: List[List[float]]) -> Dict[str, float]:
    x1, y1, x2, y2 = _bbox_bounds(bbox)
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "cx": (x1 + x2) / 2,
        "cy": (y1 + y2) / 2,
        "width": max(1.0, x2 - x1),
        "height": max(1.0, y2 - y1),
    }


def _line_blocks(structure: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
    block_to_line = structure.get("block_to_line", {})
    by_line: Dict[int, List[Dict[str, Any]]] = {}
    for block in structure.get("blocks", []):
        line_index = block_to_line.get(block["index"])
        if line_index is None:
            continue
        by_line.setdefault(line_index, []).append(block)
    for blocks in by_line.values():
        blocks.sort(key=lambda item: item["x1"])
    return by_line


def _summary_boundary_y(structure: Dict[str, Any]) -> Optional[float]:
    for line in structure.get("lines", []):
        if _norm_label(line.get("text", "")) in _SUMMARY_STOP_LABELS:
            return float(line.get("y1", 0))
    return None


def _make_segment(blocks: List[Dict[str, Any]], line: Dict[str, Any]) -> Dict[str, Any]:
    text = _clean_spaces(" ".join(block.get("text", "") for block in blocks))
    bbox = _merge_bounds(blocks)
    geom = _geometry_from_bbox(bbox)
    avg_conf = sum(float(block.get("confidence", 0) or 0) for block in blocks) / max(1, len(blocks))
    return {
        **geom,
        "text": text,
        "bbox": bbox,
        "block_indices": [block["index"] for block in blocks],
        "line_index": line.get("line_index"),
        "line_text": line.get("text", ""),
        "line_start": line.get("start", 0),
        "confidence": round(avg_conf, 4),
    }


def _label_candidates(structure: Dict[str, Any]) -> List[Dict[str, Any]]:
    labels: List[Dict[str, Any]] = []
    by_line = _line_blocks(structure)
    boundary_y = _summary_boundary_y(structure)

    for line in structure.get("lines", []):
        if boundary_y is not None and float(line.get("cy", 0)) >= boundary_y:
            continue
        blocks = by_line.get(line.get("line_index"), [])
        for start in range(len(blocks)):
            for end in range(start + 1, min(len(blocks), start + 3) + 1):
                segment_blocks = blocks[start:end]
                text = _clean_spaces(" ".join(block.get("text", "") for block in segment_blocks))
                entity_type = _LABEL_BY_ALIAS.get(_norm_label(text))
                if not entity_type:
                    continue
                segment = _make_segment(segment_blocks, line)
                labels.append({
                    **segment,
                    "entity_type": entity_type,
                    "label": text,
                })
    return labels


def _value_segments(structure: Dict[str, Any]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    by_line = _line_blocks(structure)
    boundary_y = _summary_boundary_y(structure)

    for line in structure.get("lines", []):
        if boundary_y is not None and float(line.get("cy", 0)) >= boundary_y:
            continue
        blocks = by_line.get(line.get("line_index"), [])
        max_len = min(5, len(blocks))
        for start in range(len(blocks)):
            for end in range(start + 1, min(len(blocks), start + max_len) + 1):
                segment = _make_segment(blocks[start:end], line)
                if not segment["text"] or _norm_label(segment["text"]) in _LABEL_BY_ALIAS:
                    continue
                segments.append(segment)
    return segments


def _entity_value(entity_type: str, text: str) -> str:
    text = _clean_spaces(text)
    if entity_type in {"CUSTOMER_ID", "IFSC"}:
        return re.sub(r"[^A-Z0-9]", "", text.upper())
    if entity_type == "BANK_ACCOUNT":
        return re.sub(r"\D", "", text)
    if entity_type == "ACCOUNT_BALANCE":
        match = _AMOUNT_RE.search(text)
        val = match.group(1).replace(",", "") if match else text
        # OCR artifact cleanup: Indian Rupee symbol (₹) is often misread as a duplicate of the first digit
        if len(val) >= 2 and val[0] in "237" and val[0] == val[1]:
            val = val[1:]
        return val
    return text.upper()


def _validation_confidence(entity_type: str, value: str, source_text: str, line_text: str) -> Tuple[float, str]:
    norm_label = _norm_label(source_text)
    if norm_label in _LABEL_BY_ALIAS:
        return 0.0, "candidate is a label, not a value"

    if entity_type == "CUSTOMER_ID":
        if 5 <= len(value) <= 15 and value.isalnum() and any(char.isdigit() for char in value):
            if any(char.isalpha() for char in value):
                return 0.98, "alphanumeric customer identifier with digits"
            return 0.78, "numeric customer identifier candidate"
        return 0.0, "customer id validation failed"

    if entity_type == "BANK_ACCOUNT":
        if value.isdigit() and 9 <= len(value) <= 18 and not has_transaction_context(line_text):
            return 0.97, "long numeric account number outside transaction context"
        return 0.0, "account number validation failed"

    if entity_type == "IFSC":
        if _IFSC_RE.match(value):
            return 0.99, "valid IFSC format"
        return 0.0, "IFSC validation failed"

    if entity_type == "ACCOUNT_BALANCE":
        if _AMOUNT_RE.search(source_text) or re.fullmatch(r"[0-9][0-9,]*\.\d{2}", value):
            return 0.95, "currency amount near balance label"
        return 0.0, "balance amount validation failed"

    if entity_type == "ACCOUNT_HOLDER_NAME":
        forbidden = {"NFC", "VISA", "MASTERCARD", "RUPAY", "CARD", "CVV", "EXPIRES", "BANK", "SAVINGS", "GENERAL", "BALANCE"}
        tokens = set(value.split())
        if tokens & forbidden:
            return 0.0, "name contains invalid/banking keywords"
        
        # Prevent masked card numbers (e.g. XXXX XXXX XXXX) from being identified as names
        clean_val = value.replace(" ", "").replace(".", "").replace("-", "").upper()
        if not clean_val or set(clean_val).issubset({"X", "*"}):
            return 0.0, "name consists of masking characters"

        if re.fullmatch(r"[A-Z][A-Z .'-]*(?:\s+[A-Z][A-Z .'-]*)+", value) and not re.search(r"\d", value):
            return 0.94, "multi-word alphabetic account holder name"
        return 0.0, "account holder name validation failed"

    if entity_type == "BRANCH_NAME":
        has_place_phrase = ("," in value and not value.rstrip().endswith(",")) or len(value.split()) >= 3
        if re.fullmatch(r"[A-Z][A-Z ,.'-]+", value) and not re.search(r"\d", value) and len(value) >= 6 and has_place_phrase:
            return 0.92, "alphabetic branch/location text"
        return 0.0, "branch name validation failed"

    return 0.0, "unsupported layout entity"


def _spatial_score(label: Dict[str, Any], candidate: Dict[str, Any]) -> Tuple[float, str]:
    if set(label["block_indices"]) & set(candidate["block_indices"]):
        return 0.0, "same OCR block as label"

    same_line = abs(candidate["cy"] - label["cy"]) <= max(label["height"], candidate["height"]) * 0.75
    right_of_label = candidate["x1"] >= label["x2"] - 2
    below_label = candidate["cy"] > label["cy"]
    vertical_gap = max(0.0, candidate["y1"] - label["y2"])
    x_start_delta = abs(candidate["x1"] - label["x1"])
    center_delta = abs(candidate["cx"] - label["cx"])
    horizontal_overlap = max(0.0, min(label["x2"], candidate["x2"]) - max(label["x1"], candidate["x1"]))
    overlap_ratio = horizontal_overlap / max(1.0, min(label["width"], candidate["width"]))

    if same_line and right_of_label:
        distance = max(0.0, candidate["x1"] - label["x2"])
        score = 0.88 - min(distance / 350.0, 0.45)
        return max(0.2, score), "same-row value to the right of label"

    if below_label and vertical_gap <= max(110.0, label["height"] * 5):
        aligned = overlap_ratio >= 0.25 or x_start_delta <= max(55.0, label["width"] * 0.65) or center_delta <= max(75.0, label["width"])
        if aligned:
            score = 0.94 - min(vertical_gap / 180.0, 0.40) - min(x_start_delta / 500.0, 0.15)
            return max(0.25, score), "nearest vertically aligned value below label"

    return 0.0, "not spatially aligned with label"


def _candidate_start_end(structure: Dict[str, Any], segment: Dict[str, Any], value: str) -> Tuple[int, int]:
    line_start = int(segment.get("line_start", 0))
    line_text = str(segment.get("line_text", ""))
    exact = line_text.find(value)
    if exact >= 0:
        return line_start + exact, line_start + exact + len(value)

    segment_text = str(segment.get("text", ""))
    exact = line_text.find(segment_text)
    if exact >= 0:
        offset = segment_text.find(value)
        if offset >= 0:
            return line_start + exact + offset, line_start + exact + offset + len(value)
        return line_start + exact, line_start + exact + len(segment_text)

    full_text = structure.get("full_text", "")
    exact = full_text.find(value)
    if exact >= 0:
        return exact, exact + len(value)
    return line_start, line_start + len(value)


def _score_candidate(
    label: Dict[str, Any],
    segment: Dict[str, Any],
    target_type: str,
) -> Dict[str, Any]:
    value = _entity_value(target_type, segment["text"])
    validation_conf, validation_reason = _validation_confidence(
        target_type,
        value,
        segment["text"],
        segment.get("line_text", ""),
    )
    spatial_conf, spatial_reason = _spatial_score(label, segment)
    extraction_conf = float(segment.get("confidence", 0) or 0)
    confidence = 0.0
    accepted = validation_conf > 0 and spatial_conf > 0
    rejection_reasons: List[str] = []
    if validation_conf <= 0:
        rejection_reasons.append(validation_reason)
    if spatial_conf <= 0:
        rejection_reasons.append(spatial_reason)
    if accepted:
        confidence = (extraction_conf * 0.25) + (spatial_conf * 0.35) + (validation_conf * 0.40)

    return {
        "entity_type": target_type,
        "label": label["label"],
        "candidate_text": segment["text"],
        "value": value,
        "candidate_block_indices": segment["block_indices"],
        "candidate_line_index": segment.get("line_index"),
        "candidate_bbox": segment["bbox"],
        "extraction_confidence": round(extraction_conf, 4),
        "spatial_confidence": round(spatial_conf, 4),
        "validation_confidence": round(validation_conf, 4),
        "combined_confidence": round(min(0.99, confidence), 4),
        "spatial_reason": spatial_reason,
        "validation_reason": validation_reason,
        "accepted": accepted,
        "rejection_reasons": rejection_reasons,
    }


def _candidate_decisions(
    label: Dict[str, Any],
    segments: List[Dict[str, Any]],
    target_type: str,
) -> List[Dict[str, Any]]:
    decisions = [_score_candidate(label, segment, target_type) for segment in segments]
    decisions.sort(
        key=lambda item: (
            item["accepted"],
            item["combined_confidence"],
            item["spatial_confidence"],
            item["validation_confidence"],
        ),
        reverse=True,
    )
    return decisions


def _best_value_for_label(
    structure: Dict[str, Any],
    label: Dict[str, Any],
    segments: List[Dict[str, Any]],
    entity_type: Optional[str] = None,
) -> Optional[RawMatch]:
    target_type = entity_type or label["entity_type"]
    decisions = _candidate_decisions(label, segments, target_type)

    for decision in decisions[:12]:
        logger.info(
            "Layout candidate label=%s type=%s text=%s value=%s accepted=%s spatial=%.2f validation=%.2f combined=%.2f reason=%s",
            label["label"],
            target_type,
            decision["candidate_text"],
            decision["value"],
            decision["accepted"],
            decision["spatial_confidence"],
            decision["validation_confidence"],
            decision["combined_confidence"],
            "; ".join(decision["rejection_reasons"]) or decision["spatial_reason"],
        )

    for decision in decisions:
        if not decision["accepted"]:
            continue
        segment = next(
            item for item in segments
            if item["block_indices"] == decision["candidate_block_indices"]
            and item.get("line_index") == decision.get("candidate_line_index")
        )
        value = decision["value"]
        start, end = _candidate_start_end(structure, segment, value)
        context = {
            "layout_mapping": True,
            "label": label["label"],
            "mapping_reason": f"{decision['spatial_reason']}; {decision['validation_reason']}",
            "extraction_confidence": decision["extraction_confidence"],
            "spatial_confidence": decision["spatial_confidence"],
            "validation_confidence": decision["validation_confidence"],
            "label_block_indices": label["block_indices"],
            "value_block_indices": segment["block_indices"],
            "layout_relation": decision["spatial_reason"],
            "label_bbox": label["bbox"],
            "value_bbox": segment["bbox"],
            "line_indices": sorted({label.get("line_index"), segment.get("line_index")}),
            "ocr_context": f"{label.get('line_text', label['label'])}\n{segment.get('line_text', segment['text'])}",
            "validation_checks": [decision["validation_reason"]],
            "candidate_rankings": decisions[:10],
        }
        raw = RawMatch(
            pii_type=target_type,
            value=value,
            start=start,
            end=end,
            confidence=decision["combined_confidence"],
            reason=f"Layout label-value association: {label['label']} -> {value} ({context['mapping_reason']})",
            source_rule="LayoutMapping",
            context=context,
        )
        logger.info(
            "Layout mapping selected %s label=%s value=%s confidence=%.2f reason=%s",
            raw.pii_type,
            label["label"],
            raw.value,
            raw.confidence,
            raw.context.get("mapping_reason"),
        )
        return raw
    return None


def _infer_holder_name(
    structure: Dict[str, Any],
    account_label: Dict[str, Any],
    segments: List[Dict[str, Any]],
) -> Optional[RawMatch]:
    below_segments = [
        segment for segment in segments
        if segment["cy"] > account_label["cy"]
        and segment["y1"] - account_label["y2"] <= 140
        and segment["x1"] >= account_label["x1"] - 50
        and segment["x1"] <= account_label["x2"] + 450
    ]
    below_segments.sort(key=lambda item: (item["y1"], abs(item["x1"] - account_label["x1"])))

    for segment in below_segments:
        value = _entity_value("ACCOUNT_HOLDER_NAME", segment["text"])
        validation_conf, validation_reason = _validation_confidence(
            "ACCOUNT_HOLDER_NAME",
            value,
            segment["text"],
            segment.get("line_text", ""),
        )
        if validation_conf <= 0:
            continue
            
        # Bypass strict _spatial_score, as names can align with the account number value rather than the label.
        spatial_conf = 0.85
        spatial_reason = "found alphabetic name positioned below the account row"
        extraction_conf = float(segment.get("confidence", 0) or 0)
        confidence = (extraction_conf * 0.25) + (spatial_conf * 0.35) + (validation_conf * 0.40)
        start, end = _candidate_start_end(structure, segment, value)
        context = {
            "layout_mapping": True,
            "label": "Account Holder Name",
            "mapping_reason": "Inferred holder name from alphabetic value immediately below Account Number label",
            "extraction_confidence": round(extraction_conf, 4),
            "spatial_confidence": round(spatial_conf, 4),
            "validation_confidence": round(validation_conf, 4),
            "label_block_indices": account_label["block_indices"],
            "value_block_indices": segment["block_indices"],
            "layout_relation": spatial_reason,
            "label_bbox": account_label["bbox"],
            "value_bbox": segment["bbox"],
            "line_indices": sorted({account_label.get("line_index"), segment.get("line_index")}),
            "ocr_context": f"{account_label.get('line_text', account_label['label'])}\n{segment.get('line_text', segment['text'])}",
            "validation_checks": [validation_reason],
        }
        logger.info(
            "Layout mapping inferred account holder value=%s confidence=%.2f",
            value,
            confidence,
        )
        return RawMatch(
            pii_type="ACCOUNT_HOLDER_NAME",
            value=value,
            start=start,
            end=end,
            confidence=round(min(0.99, confidence), 4),
            reason=f"Layout inference: Account Holder Name -> {value} ({context['mapping_reason']})",
            source_rule="LayoutMapping",
            document_type="",
            context=context,
        )
    return None


def extract_layout_entities(
    ocr_blocks: List[Dict[str, Any]],
    structure: Dict[str, Any],
    document_type: str,
) -> List[RawMatch]:
    if not ocr_blocks or not structure:
        return []

    labels = _label_candidates(structure)
    segments = _value_segments(structure)
    matches: List[RawMatch] = []

    for label in labels:
        match = _best_value_for_label(structure, label, segments)
        if match:
            match.document_type = document_type
            matches.append(match)

        if label["entity_type"] == "BANK_ACCOUNT":
            holder = _infer_holder_name(structure, label, segments)
            if holder:
                holder.document_type = document_type
                matches.append(holder)

    deduped: List[RawMatch] = []
    seen = set()
    for match in sorted(matches, key=lambda item: item.confidence, reverse=True):
        key = (match.pii_type, re.sub(r"[\s,-]+", "", match.value).lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(match)

    logger.info(
        "Layout mapping complete: labels=%s segments=%s matches=%s",
        len(labels),
        len(segments),
        len(deduped),
    )
    return deduped


def build_layout_debug(
    ocr_blocks: List[Dict[str, Any]],
    structure: Dict[str, Any],
    document_type: str,
) -> Dict[str, Any]:
    if not ocr_blocks or not structure:
        return {"labels": [], "value_segments": [], "decisions": [], "selected_mappings": []}

    labels = _label_candidates(structure)
    segments = _value_segments(structure)
    decisions = []
    selected_mappings = []

    for label in labels:
        candidate_rankings = _candidate_decisions(label, segments, label["entity_type"])
        selected = next((item for item in candidate_rankings if item["accepted"]), None)
        decision = {
            "entity_type": label["entity_type"],
            "label": label["label"],
            "label_block_indices": label["block_indices"],
            "label_line_index": label.get("line_index"),
            "label_bbox": label["bbox"],
            "candidate_count": len(candidate_rankings),
            "candidates": candidate_rankings[:25],
            "selected": selected,
        }
        decisions.append(decision)
        if selected:
            selected_mappings.append({
                "entity_type": label["entity_type"],
                "label": label["label"],
                "value": selected["value"],
                "confidence": selected["combined_confidence"],
                "label_bbox": label["bbox"],
                "value_bbox": selected["candidate_bbox"],
                "label_block_indices": label["block_indices"],
                "value_block_indices": selected["candidate_block_indices"],
                "mapping_reason": f"{selected['spatial_reason']}; {selected['validation_reason']}",
            })

    return {
        "document_type": document_type,
        "labels": labels,
        "value_segments": segments,
        "decisions": decisions,
        "selected_mappings": selected_mappings,
    }
