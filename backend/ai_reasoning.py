"""
ai_reasoning.py - AI reasoning layer for contextual DPDP analysis.

This service owns prompt construction, provider invocation, JSON validation,
and graceful fallback output. Routes should call this module rather than
embedding model-specific logic.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ai_providers import get_vision_provider
from prompt_formatter import prepare_prompt_payload
from risk_scoring import compute_combined_risk

logger = logging.getLogger(__name__)

ALLOWED_SEVERITIES = {"Critical", "High", "Medium", "Low", "Info"}
ALLOWED_RISKS = {"Critical", "High", "Medium", "Low"}
ALLOWED_ENTITY_TYPES = {
    "PAN",
    "AADHAAR_UNMASKED",
    "AADHAAR_MASKED",
    "EMAIL",
    "PHONE_IN",
    "DATE_OF_BIRTH",
    "CREDIT_DEBIT_CARD",
    "MASKED_CARD",
    "BANK_ACCOUNT",
    "IFSC",
    "UPI_HANDLE",
    "ACCOUNT_BALANCE",
    "CUSTOMER_ID",
    "ACCOUNT_HOLDER_NAME",
    "BRANCH_NAME",
    "TRANSACTION_REFERENCE",
    "TRANSACTION_HISTORY",
    "TRANSACTION_AMOUNT",
    "IGNORE",
}


def _safe_json_loads(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _entity_summary(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": idx + 1,
            "type": entity.get("type"),
            "raw_type": entity.get("raw_type"),
            "category": entity.get("category"),
            "risk": entity.get("risk"),
            "masked": entity.get("masked"),
            "confidence": entity.get("confidence"),
            "supporting_text": entity.get("value"),
            "reason": entity.get("reason"),
        }
        for idx, entity in enumerate(entities[:60])
    ]


def _ocr_excerpt(full_text: str, max_chars: int = 7000) -> str:
    if len(full_text) <= max_chars:
        return full_text
    return full_text[:max_chars] + "\n[OCR text truncated for analysis prompt]"


def _line_summary(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary = []
    for line in (lines or [])[:80]:
        summary.append({
            "line_index": line.get("line_index"),
            "text": line.get("text"),
            "block_indices": line.get("block_indices", []),
            "avg_confidence": line.get("avg_confidence"),
        })
    return summary


def _transaction_patterns(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    transaction_entities = [
        entity for entity in entities
        if str(entity.get("raw_type", "")).startswith("TRANSACTION")
        or entity.get("category") == "Financial Data"
    ]
    return {
        "transaction_entity_count": len(transaction_entities),
        "transaction_history_detected": any(
            entity.get("raw_type") == "TRANSACTION_HISTORY"
            for entity in transaction_entities
        ),
        "transaction_references_detected": sum(
            1 for entity in transaction_entities
            if entity.get("raw_type") == "TRANSACTION_REFERENCE"
        ),
        "financial_exposure_types": sorted({
            str(entity.get("type"))
            for entity in transaction_entities
            if entity.get("type")
        }),
    }


def _candidate_summary(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary = []
    for idx, candidate in enumerate((candidates or [])[:80]):
        summary.append({
            "candidate_id": idx + 1,
            "value": candidate.get("value"),
            "candidate_types": candidate.get("candidate_types", [])[:6],
            "ocr_block_indices": candidate.get("ocr_block_indices", []),
            "ocr_line_indices": candidate.get("ocr_line_indices", []),
            "ocr_context": str(candidate.get("ocr_context", ""))[:500],
            "bbox": candidate.get("bbox"),
        })
    return summary


def build_ai_prompt(
    *,
    ocr: Dict[str, Any],
    entities: List[Dict[str, Any]],
    compliance: Dict[str, Any],
    document_type: str,
    metadata: Dict[str, Any],
    candidate_payload: Optional[Dict[str, Any]] = None,
    semantic_resolution: Optional[Dict[str, Any]] = None,
) -> str:
    payload = {
        "document_type": document_type,
        "contextual_metadata": metadata,
        "ocr": {
            "total_blocks": ocr.get("total_blocks", 0),
            "avg_confidence": ocr.get("avg_confidence", 0),
            "full_text": _ocr_excerpt(ocr.get("full_text", "")),
            "lines": _line_summary(ocr.get("lines", [])),
        },
        "detected_pii_entities": _entity_summary(entities),
        "candidate_entities": _candidate_summary((candidate_payload or {}).get("candidates", [])),
        "semantic_resolution": {
            "status": (semantic_resolution or {}).get("status"),
            "screen_semantics": (semantic_resolution or {}).get("screen_semantics", {}),
            "entity_classifications": (semantic_resolution or {}).get("entity_classifications", [])[:80],
        },
        "transaction_patterns": _transaction_patterns(entities),
        "rule_engine_report": {
            "compliance_findings": compliance.get("flags", []),
            "by_risk": compliance.get("by_risk", {}),
            "total_entities": compliance.get("total_entities"),
        },
    }
    formatted_payload = prepare_prompt_payload(payload)

    return f"""
System instructions:
You are a DPDP banking privacy compliance analyst for multimodal screenshot
review. Use the image and the structured evidence payload together.

DPDP/RBI compliance guidance:
- Apply purpose limitation and data minimisation.
- Aadhaar should expose only last 4 digits.
- Account and card numbers should generally be masked except the minimum digits
  needed for user recognition in non-essential screens.
- PAN should be masked where full display is not necessary.
- Balances, transaction histories, beneficiary names, nominees, co-applicants,
  and transaction counterparties can create financial privacy or third-party
  exposure risk.

YAML analysis payload:
```{formatted_payload["format"]}
{formatted_payload["text"]}```

Reasoning instructions:
1. Purpose limitation: whether visible data is necessary for this screen.
2. Masking compliance: Aadhaar should expose only last 4 digits; account/card
   numbers should generally be masked except last 4 digits in non-essential
   screens; PAN should be masked where full display is not needed.
3. Third-party exposure: beneficiary, nominee, co-applicant, or transaction
   counterparty data visible beyond the user's immediate purpose.
4. Financial privacy exposure: balances, transaction history, credit limits,
   salary or spending patterns, and profiling signals.
5. Screen-level sensitivity and remediation priority.
6. If evidence is not visible in the image/OCR payload, say so through low
   confidence or omit the finding.
7. Do not invent names, account numbers, or regulatory facts.
8. Separate observations from recommendations.

Output schema instructions:
Return only strict JSON matching this schema:
{{
  "document_type": "string",
  "ai_summary": "short executive summary",
  "overall_risk": "Critical|High|Medium|Low",
  "screen_sensitivity": "Critical|High|Medium|Low",
  "purpose_limitation": {{
    "assessment": "string",
    "excessive_data_exposure": true
  }},
  "findings": [
    {{
      "issue": "string",
      "severity": "Critical|High|Medium|Low|Info",
      "reason": "why this is risky",
      "supporting_ocr": "short OCR/image evidence",
      "confidence": 0.0,
      "related_pii_entities": ["entity type or id"],
      "category": "Purpose Limitation|Masking Compliance|Third-Party Exposure|Financial Privacy|Screen-Level Risk"
    }}
  ],
  "recommendations": ["actionable remediation"],
  "observations": ["non-risk observations"],
  "limitations": ["uncertainties or missing evidence"]
}}
""".strip()


def build_entity_resolution_prompt(
    *,
    ocr: Dict[str, Any],
    candidate_payload: Dict[str, Any],
    document_type: str,
    metadata: Dict[str, Any],
) -> str:
    payload = {
        "document_type": document_type,
        "contextual_metadata": metadata,
        "ocr": {
            "total_blocks": ocr.get("total_blocks", 0),
            "avg_confidence": ocr.get("avg_confidence", 0),
            "full_text": _ocr_excerpt(ocr.get("full_text", "")),
            "lines": _line_summary(ocr.get("lines", [])),
            "rows": [
                {
                    "row_index": row.get("row_index"),
                    "text": row.get("text"),
                    "cells": [
                        {
                            "block_index": cell.get("block_index"),
                            "column_index": cell.get("column_index"),
                            "text": cell.get("text"),
                            "bbox": cell.get("bbox"),
                        }
                        for cell in (row.get("cells", [])[:12])
                    ],
                }
                for row in (ocr.get("rows", [])[:80])
            ],
        },
        "candidate_entities": _candidate_summary(candidate_payload.get("candidates", [])),
        "layout_mapping": {
            "selected_mappings": candidate_payload.get("layout_debug", {}).get("selected_mappings", [])[:30],
            "decisions": candidate_payload.get("layout_debug", {}).get("decisions", [])[:20],
        },
        "candidate_generation_stats": candidate_payload.get("stats", {}),
    }
    formatted_payload = prepare_prompt_payload(payload)

    return f"""
System instructions:
You are an AI model acting as a banking screenshot semantic entity resolver for
DPDP compliance. Use the image, OCR layout, candidate entities, bounding boxes,
rows, columns, labels, and validator evidence together.

Core rules:
- Regex candidates are evidence, not final truth.
- A 12-digit number in a UPI/IMPS/NEFT/RTGS transaction row is usually a
  transaction reference, not Aadhaar.
- Aadhaar requires Aadhaar context plus valid format/checksum evidence.
- Customer ID values are usually alphanumeric identifiers; alphabetic names
  such as account-holder names must not be classified as Customer ID.
- Banking screens contain account-summary panels, IFSC/account groupings,
  balances, transaction tables, and counterparty details.
- Names standing alone immediately above or below Bank Account numbers or Credit
  Card numbers are almost always Account Holder Names and must be classified as 
  ACCOUNT_HOLDER_NAME even without a label. (Note: Do not classify masking 
  strings like "XXXX XXXX" as Account Holder Names).
- Use visual layout and OCR coordinates to connect labels to values.
- If a candidate is not actually PII or is a label, return final_type "IGNORE".

YAML evidence payload:
```{formatted_payload["format"]}
{formatted_payload["text"]}```

Return only strict JSON matching this schema:
{{
  "status": "success",
  "document_type": "string",
  "entity_classifications": [
    {{
      "value": "exact OCR value",
      "final_type": "PAN|AADHAAR_UNMASKED|AADHAAR_MASKED|EMAIL|PHONE_IN|DATE_OF_BIRTH|CREDIT_DEBIT_CARD|MASKED_CARD|BANK_ACCOUNT|IFSC|UPI_HANDLE|ACCOUNT_BALANCE|CUSTOMER_ID|ACCOUNT_HOLDER_NAME|BRANCH_NAME|TRANSACTION_REFERENCE|TRANSACTION_HISTORY|TRANSACTION_AMOUNT|IGNORE",
      "confidence": 0.0,
      "reasoning": "why this final type was selected",
      "supporting_evidence": ["layout/visual/OCR clues"],
      "rejected_candidates": [
        {{
          "type": "candidate type rejected",
          "reason": "why rejected"
        }}
      ]
    }}
  ],
  "screen_semantics": {{
    "banking_screen_type": "Account Summary|Bank Statement|Transaction History|KYC/Profile|Other",
    "transaction_history_present": true,
    "notes": ["semantic observations"]
  }},
  "limitations": ["uncertainties"]
}}
""".strip()


def _normalize_analysis(data: Dict[str, Any], document_type: str, provider_name: str) -> Dict[str, Any]:
    findings = data.get("findings")
    if not isinstance(findings, list):
        findings = []

    normalized_findings = []
    for finding in findings[:20]:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity", "Low")).title()
        if severity not in ALLOWED_SEVERITIES:
            severity = "Low"
        confidence = finding.get("confidence", 0.5)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.5
        normalized_findings.append({
            "issue": str(finding.get("issue", "Contextual compliance concern")),
            "severity": severity,
            "reason": str(finding.get("reason", "Potential DPDP compliance risk.")),
            "supporting_ocr": str(finding.get("supporting_ocr", ""))[:500],
            "confidence": round(confidence, 2),
            "related_pii_entities": finding.get("related_pii_entities", []),
            "category": str(finding.get("category", "Screen-Level Risk")),
        })

    overall_risk = str(data.get("overall_risk", "Low")).title()
    if overall_risk not in ALLOWED_RISKS:
        overall_risk = "Low"
    screen_sensitivity = str(data.get("screen_sensitivity", overall_risk)).title()
    if screen_sensitivity not in ALLOWED_RISKS:
        screen_sensitivity = overall_risk

    purpose = data.get("purpose_limitation")
    if not isinstance(purpose, dict):
        purpose = {
            "assessment": "Purpose limitation could not be determined from the AI response.",
            "excessive_data_exposure": bool(findings),
        }

    return {
        "enabled": True,
        "provider": provider_name,
        "status": "success",
        "document_type": str(data.get("document_type") or document_type),
        "ai_summary": str(data.get("ai_summary", "AI analysis completed.")),
        "overall_risk": overall_risk,
        "screen_sensitivity": screen_sensitivity,
        "purpose_limitation": {
            "assessment": str(purpose.get("assessment", "")),
            "excessive_data_exposure": bool(purpose.get("excessive_data_exposure", False)),
        },
        "findings": normalized_findings,
        "recommendations": [
            str(item) for item in (data.get("recommendations") or [])[:12]
        ],
        "observations": [
            str(item) for item in (data.get("observations") or [])[:12]
        ],
        "limitations": [
            str(item) for item in (data.get("limitations") or [])[:8]
        ],
    }


def _normalize_entity_resolution(data: Dict[str, Any], document_type: str, provider_name: str) -> Dict[str, Any]:
    classifications = []
    for item in (data.get("entity_classifications") or [])[:100]:
        if not isinstance(item, dict):
            continue
        final_type = str(item.get("final_type", "IGNORE")).upper()
        if final_type not in ALLOWED_ENTITY_TYPES:
            final_type = "IGNORE"
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        classifications.append({
            "value": str(item.get("value", "")).strip(),
            "final_type": final_type,
            "confidence": round(confidence, 4),
            "reasoning": str(item.get("reasoning", ""))[:1000],
            "supporting_evidence": [
                str(evidence)[:300] for evidence in (item.get("supporting_evidence") or [])[:8]
            ],
            "rejected_candidates": [
                {
                    "type": str(rejected.get("type", ""))[:80],
                    "reason": str(rejected.get("reason", ""))[:300],
                }
                for rejected in (item.get("rejected_candidates") or [])[:8]
                if isinstance(rejected, dict)
            ],
        })

    screen_semantics = data.get("screen_semantics")
    if not isinstance(screen_semantics, dict):
        screen_semantics = {}

    return {
        "enabled": True,
        "provider": provider_name,
        "status": "success",
        "document_type": str(data.get("document_type") or document_type),
        "entity_classifications": classifications,
        "screen_semantics": {
            "banking_screen_type": str(screen_semantics.get("banking_screen_type", document_type)),
            "transaction_history_present": bool(screen_semantics.get("transaction_history_present", False)),
            "notes": [str(item) for item in (screen_semantics.get("notes") or [])[:8]],
        },
        "limitations": [str(item) for item in (data.get("limitations") or [])[:8]],
    }


def _heuristic_entity_resolution_fallback(
    *,
    candidate_payload: Dict[str, Any],
    document_type: str,
    provider_name: str,
    reason: str,
) -> Dict[str, Any]:
    classifications = []
    for candidate in candidate_payload.get("candidates", []):
        best = candidate.get("candidate_types", [{}])[0]
        final_type = best.get("type", "IGNORE")
        confidence = float(best.get("confidence", 0) or 0)
        if final_type == "AADHAAR_UNMASKED":
            aadhaar_validation = (best.get("validation", {}) or {}).get("aadhaar_validation", {})
            if aadhaar_validation and not aadhaar_validation.get("is_valid"):
                final_type = "IGNORE"
                confidence = min(confidence, 0.2)
        classifications.append({
            "value": candidate.get("value", ""),
            "final_type": final_type,
            "confidence": round(confidence, 4),
            "reasoning": "AI semantic resolver unavailable; selected highest-confidence deterministic candidate evidence.",
            "supporting_evidence": [candidate.get("ocr_context", "")],
            "rejected_candidates": [],
        })

    return {
        "enabled": False,
        "provider": provider_name,
        "status": "fallback",
        "error": reason,
        "document_type": document_type,
        "entity_classifications": classifications,
        "screen_semantics": {
            "banking_screen_type": document_type,
            "transaction_history_present": any(
                any(item.get("type") == "TRANSACTION_HISTORY" for item in candidate.get("candidate_types", []))
                for candidate in candidate_payload.get("candidates", [])
            ),
            "notes": ["AI semantic resolver fallback used deterministic candidate evidence."],
        },
        "limitations": ["AI semantic entity resolution was unavailable."],
    }


def analyze_entity_candidates(
    *,
    image_bytes: bytes,
    mime_type: str,
    ocr: Dict[str, Any],
    candidate_payload: Dict[str, Any],
    document_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = metadata or {}
    provider_name = "unknown"
    try:
        provider = get_vision_provider()
        provider_name = getattr(provider, "name", provider_name)
        prompt = build_entity_resolution_prompt(
            ocr=ocr,
            candidate_payload=candidate_payload,
            document_type=document_type,
            metadata=metadata,
        )
        raw = provider.analyze(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt,
            max_tokens=2600,
        )
        return _normalize_entity_resolution(_safe_json_loads(raw), document_type, provider_name)
    except Exception as exc:
        logger.warning("AI semantic entity resolver unavailable; using fallback: %s", exc)
        return _heuristic_entity_resolution_fallback(
            candidate_payload=candidate_payload,
            document_type=document_type,
            provider_name=provider_name,
            reason=str(exc),
        )


def _heuristic_fallback(
    *,
    entities: List[Dict[str, Any]],
    compliance: Dict[str, Any],
    document_type: str,
    provider_name: str,
    reason: str,
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    recommendations = set()

    for entity in entities:
        raw_type = entity.get("raw_type")
        risk = entity.get("risk", "Low")
        if entity.get("masked") or risk not in {"Critical", "High"}:
            continue
        if raw_type in {"AADHAAR_UNMASKED", "CREDIT_DEBIT_CARD", "BANK_ACCOUNT", "PAN"}:
            findings.append({
                "issue": f"{entity.get('type', 'Sensitive data')} appears overexposed",
                "severity": "Critical" if risk == "Critical" else "High",
                "reason": entity.get("reason") or "Sensitive identifier is visible without sufficient masking.",
                "supporting_ocr": entity.get("value", ""),
                "confidence": entity.get("confidence", 0.7),
                "related_pii_entities": [entity.get("type")],
                "category": "Masking Compliance",
            })
            recommendations.add("Mask sensitive identifiers except the minimum digits required for the user task.")
        elif raw_type in {"ACCOUNT_BALANCE", "TRANSACTION_HISTORY"}:
            findings.append({
                "issue": f"{entity.get('type', 'Financial data')} is visible",
                "severity": "High",
                "reason": "Financial activity and balances can reveal sensitive profiling information.",
                "supporting_ocr": entity.get("value", ""),
                "confidence": entity.get("confidence", 0.7),
                "related_pii_entities": [entity.get("type")],
                "category": "Financial Privacy",
            })
            recommendations.add("Limit balance and transaction visibility to screens with a clear business purpose.")

    for flag in compliance.get("flags", [])[:6]:
        recommendations.add(str(flag).replace("DPDP Violation:", "").replace("DPDP Guidance:", "").strip())

    highest = "Low"
    for severity in ["Critical", "High", "Medium"]:
        if any(f["severity"] == severity for f in findings):
            highest = severity
            break

    return {
        "enabled": False,
        "provider": provider_name,
        "status": "fallback",
        "error": reason,
        "document_type": document_type,
        "ai_summary": (
            "AI Vision analysis was unavailable, so the dashboard is showing "
            "rule-based contextual DPDP findings."
        ),
        "overall_risk": highest,
        "screen_sensitivity": "High" if document_type in {"Bank Statement", "KYC Form", "Passbook Screen"} else highest,
        "purpose_limitation": {
            "assessment": "Purpose limitation requires AI vision review; fallback used deterministic PII exposure rules.",
            "excessive_data_exposure": bool(findings),
        },
        "findings": findings,
        "recommendations": list(recommendations)[:12],
        "observations": ["OCR and rule-based PII analysis completed successfully."],
        "limitations": ["AI provider was unavailable; image-level reasoning was not performed."],
    }


def analyze_dpdp_compliance(
    *,
    image_bytes: bytes,
    mime_type: str,
    ocr: Dict[str, Any],
    entities: List[Dict[str, Any]],
    compliance: Dict[str, Any],
    document_type: str,
    candidate_payload: Optional[Dict[str, Any]] = None,
    semantic_resolution: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = metadata or {}
    provider_name = "unknown"
    try:
        provider = get_vision_provider()
        provider_name = getattr(provider, "name", provider_name)
        prompt = build_ai_prompt(
            ocr=ocr,
            entities=entities,
            compliance=compliance,
            document_type=document_type,
            metadata=metadata,
            candidate_payload=candidate_payload,
            semantic_resolution=semantic_resolution,
        )
        raw = provider.analyze(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt,
        )
        ai_analysis = _normalize_analysis(_safe_json_loads(raw), document_type, provider_name)
    except Exception as exc:
        logger.warning("AI reasoning unavailable; using fallback: %s", exc)
        ai_analysis = _heuristic_fallback(
            entities=entities,
            compliance=compliance,
            document_type=document_type,
            provider_name=provider_name,
            reason=str(exc),
        )

    ai_analysis["risk_score"] = compute_combined_risk(
        rule_compliance=compliance,
        entities=entities,
        ai_analysis=ai_analysis,
        document_type=document_type,
    )
    return ai_analysis
