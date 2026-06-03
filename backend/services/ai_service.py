"""
services/ai_service.py  —  Text-based AI reasoning service for DPDP Compliance Scanner
========================================================================================
Calls SambaNova's OpenAI-compatible chat-completions endpoint with AI model.
Uses only stdlib (json, urllib) — no new pip dependencies required.

Responsibilities:
  1. Build a YAML-compacted prompt from OCR + entity + compliance context
  2. POST to SambaNova /v1/chat/completions
  3. Parse + validate JSON response
  4. Return structured DPDP reasoning

Config (all in backend/.env):
  SAMBANOVA_API_KEY  — your SambaNova API key
  SAMBANOVA_MODEL    — model slug (default: AI_MODEL)
  SAMBANOVA_BASE_URL — API base URL (default: https://api.sambanova.ai/v1)
"""

import json
import logging
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
SAMBANOVA_API_KEY:  str   = os.getenv("AI_API_KEY") or os.getenv("SAMBANOVA_API_KEY", "")
SAMBANOVA_MODEL:    str   = os.getenv("AI_MODEL") or os.getenv("SAMBANOVA_MODEL",   "AI_MODEL")
SAMBANOVA_BASE_URL: str   = (os.getenv("AI_BASE_URL") or os.getenv("SAMBANOVA_BASE_URL", "https://api.sambanova.ai/v1")).rstrip("/")
SAMBANOVA_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS") or os.getenv("SAMBANOVA_MAX_TOKENS", "2048"))
SAMBANOVA_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE") or os.getenv("SAMBANOVA_TEMPERATURE", "0.1"))
SAMBANOVA_TIMEOUT:  int   = int(os.getenv("AI_TIMEOUT_SECONDS") or os.getenv("SAMBANOVA_TIMEOUT_SECONDS", "90"))

# Keep HF_TEXT_MODEL as an alias so main.py import doesn't break
HF_TEXT_MODEL: str = SAMBANOVA_MODEL

ALLOWED_SEVERITIES = {"Critical", "High", "Medium", "Low", "Info"}
ALLOWED_RISKS      = {"Critical", "High", "Medium", "Low"}


# ── SambaNova inference ────────────────────────────────────────────────────────

def _call_sambanova(
    messages: list,
    max_tokens: int,
    temperature: float,
) -> str:
    """
    POST to SambaNova's OpenAI-compatible /v1/chat/completions.
    Returns the raw assistant message content string.
    Raises RuntimeError on any failure.
    """
    if not SAMBANOVA_API_KEY:
        raise RuntimeError(
            "SAMBANOVA_API_KEY is not set. "
            "Add your SambaNova API key to backend/.env."
        )

    payload = {
        "model":       SAMBANOVA_MODEL,
        "messages":    messages,
        "max_tokens":  max_tokens,
        "temperature": temperature,
    }
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        f"{SAMBANOVA_BASE_URL}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    # Bypass SSL verification since Windows Python often fails on standard CA certs
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=SAMBANOVA_TIMEOUT, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise RuntimeError(f"SambaNova HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"SambaNova request failed: {exc}") from exc

    try:
        return result["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected SambaNova response shape: {result}") from exc



# ── Payload helpers ────────────────────────────────────────────────────────────

def _ocr_excerpt(full_text: str, max_chars: int = 5000) -> str:
    if len(full_text) <= max_chars:
        return full_text
    return full_text[:max_chars] + "\n[truncated]"


def _entity_rows(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id":         idx + 1,
            "type":       e.get("type"),
            "raw_type":   e.get("raw_type"),
            "category":   e.get("category"),
            "risk":       e.get("risk"),
            "masked":     e.get("masked"),
            "confidence": e.get("confidence"),
            "value":      e.get("value"),
            "reason":     e.get("reason"),
        }
        for idx, e in enumerate(entities[:50])
    ]


def _transaction_summary(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    fin = [e for e in entities if e.get("category") == "Financial Data"]
    return {
        "financial_entity_count":      len(fin),
        "transaction_history_present": any(e.get("raw_type") == "TRANSACTION_HISTORY" for e in fin),
        "transaction_references":      sum(1 for e in fin if e.get("raw_type") == "TRANSACTION_REFERENCE"),
        "financial_types":             sorted({str(e.get("type")) for e in fin if e.get("type")}),
    }


def _build_yaml_payload(
    *,
    document_type: str,
    ocr: Dict[str, Any],
    entities: List[Dict[str, Any]],
    compliance: Dict[str, Any],
    metadata: Dict[str, Any],
) -> str:
    """
    Convert the analysis context to compact YAML.
    Falls back to JSON if YAML serialisation fails.
    """
    payload: Dict[str, Any] = {
        "document_type":   document_type,
        "metadata":        metadata,
        "ocr": {
            "total_blocks":   ocr.get("total_blocks", 0),
            "avg_confidence": ocr.get("avg_confidence", 0),
            "full_text":      _ocr_excerpt(ocr.get("full_text", "")),
        },
        "detected_pii_entities":  _entity_rows(entities),
        "transaction_patterns":   _transaction_summary(entities),
        "rule_engine": {
            "by_risk":  compliance.get("by_risk", {}),
            "flags":    compliance.get("flags", [])[:10],
        },
    }

    try:
        import yaml  # pyyaml is a huggingface_hub dependency
        return yaml.dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False)
    except Exception:
        return json.dumps(payload, ensure_ascii=False, indent=2)


# ── Prompt construction ────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a DPDP (Digital Personal Data Protection Act, 2023) compliance evaluator for banking app screenshots.

Your task is to evaluate whether the screenshot violates any sections of the DPDP Act 2023.

DPDP ACT 2023 — SECTIONS TO EVALUATE:
  Section 4: Grounds for processing — personal data may only be processed for lawful purposes with consent or legitimate uses.
  Section 5(1): Notice — every consent request must be accompanied/preceded by a notice specifying (i) personal data and purpose, (ii) how to exercise rights, (iii) how to complain to Board.
  Section 5(1)(i): Notice must specify purpose of processing.
  Section 5(1)(ii): Notice must inform Data Principal how to exercise rights.
  Section 5(1)(iii): Notice must inform how to complain to the Board.
  Section 5(2): Pre-existing consent — if consent was given before Act commencement, notice must be given as soon as practicable.
  Section 5(3): Language — notice must be in English or any Eighth Schedule language.
  Section 6(1): Consent — must be free, specific, informed, unconditional, unambiguous; limited to data necessary for specified purpose (data minimisation).
  Section 6(2): Invalid consent — any part infringing the Act is invalid.
  Section 6(3): Consent language — requests must be in clear, plain language with DPO contact.
  Section 6(4): Right to withdraw consent — Data Principal may withdraw consent at any time.
  Section 6(6): Cessation — Data Fiduciary must cease processing after consent withdrawal.
  Section 6(7): Consent Manager — Data Principal may manage consent through a Consent Manager.
  Section 7: Certain legitimate uses — voluntary provision, State functions, legal obligations, medical emergencies, employment.
  Section 8(1): Compliance responsibility — Data Fiduciary responsible regardless of agreements.
  Section 8(3): Data accuracy — must ensure completeness, accuracy, consistency when data used for decisions or shared.
  Section 8(4): Technical measures — must implement appropriate technical and organisational measures.
  Section 8(5): Security safeguards — must protect personal data with reasonable security safeguards to prevent breach.
  Section 8(6): Breach notification — must notify Board and affected Data Principals of breach.
  Section 8(7): Data retention/erasure — must erase data when consent withdrawn or purpose no longer served.
  Section 8(9): DPO contact — must publish DPO business contact information.
  Section 8(10): Grievance redressal — must establish effective grievance redressal mechanism.
  Section 9(1): Children — must obtain verifiable parental/guardian consent.
  Section 9(2): No detrimental processing — must not process data detrimentally affecting child.
  Section 9(3): No tracking/targeting children — must not track, behaviourally monitor, or target advertising at children.
  Section 10: Significant Data Fiduciary — must appoint DPO, independent auditor, conduct DPIA.
  Section 11: Right to access — Data Principal can request summary of data processed.
  Section 12: Right to correction and erasure — right to correct, complete, update, erase.
  Section 13: Right of grievance redressal — Data Principal has right to grievance redressal.
  Section 16: Cross-border transfer — restrictions on transfer of personal data outside India.

CRITICAL RULES:
  - Every violation MUST cite: the specific Act section(s) violated, the PII entities involved, a clear finding.
  - Severity has exactly 4 levels: CRITICAL, HIGH, MEDIUM, LOW.
  - "No violations" is only valid AFTER checking all areas: consent, notice, data minimisation, security, children's data, retention, third-party sharing, grievance redressal.
  - INCONCLUSIVE is valid when OCR confidence is insufficient or masking cannot be confirmed.
  - Transaction IDs (12-20 digits in UPI/NEFT/RTGS rows) are NOT Aadhaar numbers.

COMPLIANCE AREAS TO CHECK:
  1. Data Minimisation (Section 6(1)) — is more data displayed than necessary for the screen's purpose?
  2. Consent & Notice (Sections 5, 6) — is consent/notice visible where PII is collected?
  3. Data Security (Section 8(5)) — are passwords, OTPs, credentials, or full card/Aadhaar numbers visible?
  4. Data Retention (Section 8(7)) — is data retained beyond its purpose (e.g., KYC data in transaction history)?
  5. Children's Data (Section 9) — is a minor's account detected without guardian consent?
  6. Third-Party Sharing (Sections 4, 8(3)) — is PII visible alongside third-party content without disclosure?
  7. Sensitive Data (Sections 4, 6(1)) — is religion/caste/biometric data visible without lawful purpose?
  8. Grievance Redressal (Section 8(10)) — is DPO contact or grievance mechanism visible on PII-heavy screens?
  9. Data Accuracy (Section 8(3)) — are there conflicting data values on the same screen?

Return ONLY strict JSON (no markdown, no explanation outside the JSON) matching:
{
  "violations_found": "YES|NO|INCONCLUSIVE",
  "overall_risk": "CRITICAL|HIGH|MEDIUM|LOW",
  "screen_sensitivity": "CRITICAL|HIGH|MEDIUM|LOW",
  "violation_details": [
    {
      "act_section": "Section X(Y)",
      "section_title": "short title of the section",
      "pii_involved": ["entity type or description"],
      "finding": "one sentence describing the violation",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "confidence": 0.0,
      "category": "Data Minimisation|Consent & Notice|Data Security|Data Retention|Children's Data|Third-Party Sharing|Sensitive Data|Grievance Redressal|Data Accuracy",
      "penalty_reference": "applicable penalty from Schedule (e.g., Up to 250 crore)"
    }
  ],
  "purpose_limitation": {
    "assessment": "string",
    "excessive_data_exposure": true
  },
  "ai_summary": "1-2 sentence executive summary",
  "recommendations": ["actionable remediation"],
  "observations": ["non-risk observations"],
  "limitations": ["uncertainties or missing evidence"]
}"""


def _build_user_message(yaml_payload: str) -> str:
    return (
        "Analyse the following banking OCR extraction payload for DPDP compliance.\n\n"
        "```yaml\n"
        f"{yaml_payload}"
        "```\n\n"
        "Return only the JSON result as described in the system instructions."
    )


# ── Response parsing ────────────────────────────────────────────────────────────

def _parse_json_response(raw: str) -> Dict[str, Any]:
    """
    Attempt to extract a JSON object from the model's reply.
    AI models may wrap output in <think>...</think> tags; strip those first.
    """
    # Strip AI model chain-of-thought block
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences and retry
    fenced = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    fenced = re.sub(r"```\s*$", "", fenced, flags=re.MULTILINE).strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass

    # Last resort: extract first {...} block
    match = re.search(r"\{.*\}", fenced, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not extract JSON from model response. Raw (first 500): {raw[:500]}")


# ── Response normalisation ─────────────────────────────────────────────────────

def _normalize(
    data: Dict[str, Any],
    document_type: str,
    model: str,
    latency_ms: float,
) -> Dict[str, Any]:
    # Normalize violation_details — now section-based, no rule_id
    violation_details = []
    for v in (data.get("violation_details") or [])[:20]:
        if not isinstance(v, dict):
            continue
        sev = str(v.get("severity", "LOW")).strip().upper()
        if sev not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            sev = "LOW"
        try:
            conf = round(max(0.0, min(1.0, float(v.get("confidence", 0.7)))), 2)
        except (TypeError, ValueError):
            conf = 0.7
        violation_details.append({
            "act_section":      str(v.get("act_section", ""))[:50],
            "section_title":    str(v.get("section_title", ""))[:100],
            "pii_involved":     list(v.get("pii_involved") or [])[:8],
            "finding":          str(v.get("finding", ""))[:300],
            "severity":         sev,
            "confidence":       conf,
            "category":         str(v.get("category", ""))[:80],
            "penalty_reference": str(v.get("penalty_reference", ""))[:100],
        })

    # Build legacy findings from violation_details for backward compat
    findings = []
    for v in violation_details:
        findings.append({
            "issue":               f"[{v['act_section']}] {v['finding']}",
            "severity":            v["severity"].title(),
            "reason":              f"Act {v['act_section']} ({v['section_title']}): {v['finding']}",
            "supporting_ocr":      "",
            "confidence":          v["confidence"],
            "related_pii_entities": v["pii_involved"],
            "category":            v["category"],
        })

    overall_risk = str(data.get("overall_risk", "LOW")).strip().upper()
    if overall_risk not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        overall_risk = "LOW"

    screen_sens = str(data.get("screen_sensitivity", overall_risk)).strip().upper()
    if screen_sens not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        screen_sens = overall_risk

    purpose = data.get("purpose_limitation") or {}
    if not isinstance(purpose, dict):
        purpose = {}

    violations_found = str(data.get("violations_found", "NO")).strip().upper()
    if violations_found not in {"YES", "NO", "INCONCLUSIVE"}:
        violations_found = "YES" if violation_details else "NO"

    return {
        "enabled":          True,
        "provider":         "sambanova",
        "model":            model,
        "status":           "success",
        "latency_ms":       round(latency_ms, 1),
        "document_type":    str(data.get("document_type") or document_type),
        "violations_found": violations_found,
        "ai_summary":       str(data.get("ai_summary", "AI analysis completed."))[:600],
        "overall_risk":     overall_risk,
        "screen_sensitivity": screen_sens,
        "purpose_limitation": {
            "assessment":            str(purpose.get("assessment", ""))[:600],
            "excessive_data_exposure": bool(purpose.get("excessive_data_exposure", False)),
        },
        "violation_details": violation_details,
        "findings":         findings,
        "recommendations":  [str(r)[:300] for r in (data.get("recommendations") or [])[:12]],
        "observations":     [str(o)[:300] for o in (data.get("observations") or [])[:12]],
        "limitations":      [str(l)[:200] for l in (data.get("limitations") or [])[:8]],
    }


# ── Fallback ────────────────────────────────────────────────────────────────────

def _heuristic_fallback(
    *,
    entities: List[Dict[str, Any]],
    compliance: Dict[str, Any],
    document_type: str,
    reason: str,
) -> Dict[str, Any]:
    """Deterministic fallback when HF inference is unavailable."""
    findings: List[Dict[str, Any]] = []
    recs = set()
    for e in entities:
        rt   = e.get("raw_type", "")
        risk = e.get("risk", "Low")
        if e.get("masked") or risk not in {"Critical", "High"}:
            continue
        if rt in {"AADHAAR_UNMASKED", "CREDIT_DEBIT_CARD", "BANK_ACCOUNT", "PAN"}:
            findings.append({
                "issue":               f"{e.get('type', 'Sensitive data')} is overexposed",
                "severity":            "Critical" if risk == "Critical" else "High",
                "reason":              e.get("reason") or "Sensitive identifier visible without masking.",
                "supporting_ocr":      str(e.get("value", ""))[:200],
                "confidence":          float(e.get("confidence", 0.7)),
                "related_pii_entities": [e.get("type", rt)],
                "category":            "Masking Compliance",
            })
            recs.add("Mask sensitive identifiers; display only the minimum required digits.")
        elif rt in {"ACCOUNT_BALANCE", "TRANSACTION_HISTORY"}:
            findings.append({
                "issue":               f"{e.get('type', 'Financial data')} is visible",
                "severity":            "High",
                "reason":              "Financial activity and balances reveal sensitive profiling data.",
                "supporting_ocr":      str(e.get("value", ""))[:200],
                "confidence":          float(e.get("confidence", 0.7)),
                "related_pii_entities": [e.get("type", rt)],
                "category":            "Financial Privacy",
            })
            recs.add("Limit balance/transaction visibility to screens with a clear business purpose.")

    highest = "Low"
    for sev in ("Critical", "High", "Medium"):
        if any(f["severity"] == sev for f in findings):
            highest = sev
            break

    return {
        "enabled":          False,
        "provider":         "sambanova",
        "model":            SAMBANOVA_MODEL,
        "status":           "fallback",
        "error":            reason,
        "document_type":    document_type,
        "ai_summary":       "Rule-based DPDP analysis completed; AI reasoning was unavailable.",
        "overall_risk":     highest,
        "screen_sensitivity": "High" if document_type in {"Bank Statement", "KYC Form", "Passbook Screen"} else highest,
        "purpose_limitation": {
            "assessment":            "Purpose limitation requires AI reasoning; deterministic fallback used.",
            "excessive_data_exposure": bool(findings),
        },
        "findings":         findings,
        "recommendations":  list(recs)[:12],
        "observations":     ["OCR and rule-based PII analysis completed successfully."],
        "limitations":      [f"SambaNova inference unavailable: {reason[:200]}"],
    }


# ── Public API ──────────────────────────────────────────────────────────────────

def run_text_analysis(
    *,
    document_type: str,
    ocr: Dict[str, Any],
    entities: List[Dict[str, Any]],
    compliance: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entry point.

    Builds a YAML evidence payload → calls AI model via SambaNova
    → parses + normalises the JSON response.

    Always returns a dict; falls back deterministically if inference fails.
    """
    metadata = metadata or {}

    # ── Build payload ───────────────────────────────────────────────────────
    yaml_payload = _build_yaml_payload(
        document_type=document_type,
        ocr=ocr,
        entities=entities,
        compliance=compliance,
        metadata=metadata,
    )
    token_estimate = max(1, len(yaml_payload) // 4)
    logger.info(
        "[ai_service] Payload built: doc_type=%s entities=%d yaml_chars=%d ~%d tokens",
        document_type, len(entities), len(yaml_payload), token_estimate,
    )

    # ── Inference ───────────────────────────────────────────────────────
    t0 = time.monotonic()
    try:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": _build_user_message(yaml_payload)},
        ]
        logger.info(
            "[ai_service] Calling SambaNova: model=%s base_url=%s",
            SAMBANOVA_MODEL, SAMBANOVA_BASE_URL,
        )
        raw_text = _call_sambanova(
            messages=messages,
            max_tokens=SAMBANOVA_MAX_TOKENS,
            temperature=SAMBANOVA_TEMPERATURE,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "[ai_service] SambaNova OK: latency=%.0fms response_chars=%d",
            latency_ms, len(raw_text),
        )

    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        logger.error(
            "[ai_service] SambaNova FAILED after %.0fms: %s",
            latency_ms, exc,
        )
        return _heuristic_fallback(
            entities=entities,
            compliance=compliance,
            document_type=document_type,
            reason=str(exc),
        )

    # ── Parse & normalise ─────────────────────────────────────────────
    try:
        data = _parse_json_response(raw_text)
        result = _normalize(data, document_type, SAMBANOVA_MODEL, latency_ms)
        logger.info(
            "[ai_service] Parsed OK: overall_risk=%s findings=%d",
            result["overall_risk"], len(result["findings"]),
        )
        return result
    except Exception as exc:
        logger.error("[ai_service] JSON parse failed: %s. Raw: %s", exc, raw_text[:300])
        return _heuristic_fallback(
            entities=entities,
            compliance=compliance,
            document_type=document_type,
            reason=f"Response parse error: {exc}",
        )
