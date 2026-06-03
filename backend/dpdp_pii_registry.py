"""
dpdp_pii_registry.py — DPDP Act PII Detection Registry (PART A)
================================================================
Maps internal entity types to the formal DPDP PII parameter IDs.
Provides scan_pii_inventory() to build a PRESENT/ABSENT map.
"""

import re
import logging
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

PII_REGISTRY = {
    "KYC-01": {"name": "PAN Details", "group": "KYC Documents"},
    "KYC-02": {"name": "Aadhaar Details", "group": "KYC Documents"},
    "KYC-03": {"name": "Passport Details", "group": "KYC Documents"},
    "KYC-04": {"name": "Voter ID", "group": "KYC Documents"},
    "KYC-05": {"name": "Driving Licence", "group": "KYC Documents"},
    "ID-01": {"name": "Full Name", "group": "Identity Data"},
    "ID-02": {"name": "Customer ID", "group": "Identity Data"},
    "ID-03": {"name": "Photograph", "group": "Identity Data"},
    "ID-04": {"name": "Date of Birth", "group": "Identity Data"},
    "ID-05": {"name": "Gender", "group": "Identity Data"},
    "ID-06": {"name": "Location / Geo", "group": "Identity Data"},
    "ID-07": {"name": "Residential Address", "group": "Identity Data"},
    "ID-08": {"name": "Nationality", "group": "Identity Data"},
    "ID-09": {"name": "Spouse Name", "group": "Identity Data"},
    "ID-10": {"name": "Dependent Details", "group": "Identity Data"},
    "ID-11": {"name": "Insurance Details", "group": "Identity Data"},
    "ID-12": {"name": "Certificate", "group": "Identity Data"},
    "ID-13": {"name": "Personal Email ID", "group": "Identity Data"},
    "ID-14": {"name": "Personal Phone Number", "group": "Identity Data"},
    "ID-15": {"name": "Signature", "group": "Identity Data"},
    "ID-16": {"name": "Utility Bills", "group": "Identity Data"},
    "ID-17": {"name": "Religion", "group": "Identity Data"},
    "ID-18": {"name": "Reservation Category", "group": "Identity Data"},
    "ID-19": {"name": "Ration Number", "group": "Identity Data"},
    "ID-20": {"name": "Caste Certificate", "group": "Identity Data"},
    "FIN-01": {"name": "Bank Account Number", "group": "Financial Data"},
    "FIN-02": {"name": "Debit Card Details", "group": "Financial Data"},
    "FIN-03": {"name": "Credit Card Details", "group": "Financial Data"},
    "FIN-04": {"name": "Credit Score", "group": "Financial Data"},
    "FIN-05": {"name": "Bank Statements", "group": "Financial Data"},
    "FIN-06": {"name": "UPI Handle", "group": "Financial Data"},
    "FIN-07": {"name": "Account Balance", "group": "Financial Data"},
    "FIN-08": {"name": "Transaction History", "group": "Financial Data"},
    "FIN-09": {"name": "Income Proof", "group": "Financial Data"},
    "FIN-10": {"name": "Tax Returns", "group": "Financial Data"},
    "FIN-11": {"name": "CTC Data", "group": "Financial Data"},
    "BIO-01": {"name": "Fingerprints", "group": "Biometric Data"},
    "BIO-02": {"name": "Voice Patterns", "group": "Biometric Data"},
    "ONL-01": {"name": "Username", "group": "Online Identifiers"},
    "ONL-02": {"name": "Password", "group": "Online Identifiers"},
    "ONL-03": {"name": "IP Address", "group": "Online Identifiers"},
    "ONL-04": {"name": "Cookie / Session", "group": "Online Identifiers"},
    "CHD-01": {"name": "Child Name", "group": "Children Data"},
    "CHD-02": {"name": "Child DOB", "group": "Children Data"},
    "CHD-03": {"name": "Guardian Name", "group": "Children Data"},
    "CHD-04": {"name": "Disability Status", "group": "Children Data"},
    "CHD-05": {"name": "Disability Certificate", "group": "Children Data"},
    "OTH-01": {"name": "Voice Recording", "group": "Other Sensitive"},
    "OTH-02": {"name": "Video Recording", "group": "Other Sensitive"},
    "OTH-03": {"name": "CCTV Footage", "group": "Other Sensitive"},
}

ENTITY_TO_PII_IDS: Dict[str, List[str]] = {
    "PAN": ["KYC-01"],
    "AADHAAR_UNMASKED": ["KYC-02"],
    "AADHAAR_MASKED": ["KYC-02"],
    "ACCOUNT_HOLDER_NAME": ["ID-01"],
    "CUSTOMER_ID": ["ID-02"],
    "DATE_OF_BIRTH": ["ID-04"],
    "EMAIL": ["ID-13"],
    "PHONE_IN": ["ID-14"],
    "BANK_ACCOUNT": ["FIN-01"],
    "CREDIT_DEBIT_CARD": ["FIN-02", "FIN-03"],
    "MASKED_CARD": ["FIN-02", "FIN-03"],
    "UPI_HANDLE": ["FIN-06"],
    "ACCOUNT_BALANCE": ["FIN-07"],
    "TRANSACTION_HISTORY": ["FIN-08"],
    "TRANSACTION_REFERENCE": ["FIN-08"],
    "TRANSACTION_AMOUNT": ["FIN-08"],
    "IFSC": ["FIN-01"],
    "_KW_PASSWORD": ["ONL-02"],
}

_OCR_SIGNALS: Dict[str, List[str]] = {
    "KYC-03": [r"\bpassport\b"],
    "KYC-04": [r"\bvoter\s*id\b", r"\bepic\b"],
    "KYC-05": [r"\bdriving\s*licen[cs]e\b"],
    "ID-03": [r"\bphoto(?:graph)?\b"],
    "ID-05": [r"\bgender\b"],
    "ID-06": [r"\blocation\b"],
    "ID-07": [r"\b(?:address|residence)\b"],
    "ID-08": [r"\bnationality\b"],
    "ID-09": [r"\bspouse\b", r"\bjoint\s*holder\b"],
    "ID-10": [r"\b(?:dependent|nominee)\b"],
    "ID-11": [r"\binsurance\b"],
    "ID-15": [r"\bsignature\b"],
    "ID-17": [r"\breligion\b"],
    "ID-18": [r"\bcaste\s*category\b", r"\breservation\b"],
    "ID-20": [r"\bcaste\b", r"\bcommunity\s*certificate\b"],
    "FIN-04": [r"\bcibil\b", r"\bcredit\s*score\b"],
    "FIN-05": [r"\bstatement\b", r"\bpassbook\b"],
    "FIN-09": [r"\bsalary\b", r"\bincome\b", r"\bform\s*16\b"],
    "FIN-10": [r"\bitr\b", r"\btax\s*return\b"],
    "FIN-11": [r"\bctc\b", r"\bgross\s*salary\b"],
    "BIO-01": [r"\bfingerprint\b"],
    "BIO-02": [r"\bvoice\b.*\bauth\b"],
    "ONL-01": [r"\busername\b", r"\buser\s*id\b", r"\blogin\s*id\b"],
    "ONL-03": [r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"],
    "ONL-04": [r"\bsession\b", r"\btoken\b"],
    "CHD-01": [r"\bminor\b", r"\bchild\s*name\b"],
    "CHD-03": [r"\bguardian\b", r"\bparent\s*name\b"],
    "CHD-04": [r"\bdisabilit(?:y|ies)\b", r"\bpwd\b"],
    "OTH-01": [r"\bcall\s*recording\b"],
    "OTH-02": [r"\bvideo\s*kyc\b"],
    "OTH-03": [r"\bcctv\b"],
}


def scan_pii_inventory(
    entities: List[Dict[str, Any]],
    ocr_full_text: str,
) -> Dict[str, str]:
    """Build PRESENT/ABSENT map for every PII parameter in PART A."""
    present: Set[str] = set()

    for entity in entities:
        raw_type = entity.get("raw_type", "")
        present.update(ENTITY_TO_PII_IDS.get(raw_type, []))

    text_lower = ocr_full_text.lower()
    for pii_id, patterns in _OCR_SIGNALS.items():
        if pii_id in present:
            continue
        for pat in patterns:
            if re.search(pat, text_lower):
                present.add(pii_id)
                break

    inventory = {pid: ("PRESENT" if pid in present else "ABSENT") for pid in sorted(PII_REGISTRY)}
    logger.info("[PII Registry] %d/%d PRESENT", sum(1 for v in inventory.values() if v == "PRESENT"), len(inventory))
    return inventory


def get_present_pii_ids(inventory: Dict[str, str]) -> Set[str]:
    return {k for k, v in inventory.items() if v == "PRESENT"}


def get_pii_name(pii_id: str) -> str:
    entry = PII_REGISTRY.get(pii_id)
    return entry["name"] if entry else pii_id
