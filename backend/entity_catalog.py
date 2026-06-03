"""
entity_catalog.py - shared entity metadata for candidate and final entities.
"""

from typing import Dict


CATEGORY_MAP: Dict[str, str] = {
    "PAN": "KYC Documents",
    "AADHAAR_UNMASKED": "KYC Documents",
    "AADHAAR_MASKED": "KYC Documents",
    "PASSPORT": "KYC Documents",
    "VOTER_ID": "KYC Documents",
    "DRIVING_LICENCE": "KYC Documents",
    "EMAIL": "Identity Data",
    "PHONE_IN": "Identity Data",
    "DATE_OF_BIRTH": "Identity Data",
    "_KW_PHOTOGRAPH": "Identity Data",
    "_KW_SIGNATURE": "Identity Data",
    "CREDIT_DEBIT_CARD": "Financial Data",
    "MASKED_CARD": "Financial Data",
    "BANK_ACCOUNT": "Financial Data",
    "IFSC": "Financial Data",
    "UPI_HANDLE": "Financial Data",
    "IP_ADDRESS": "Online Identifiers",
    "_KW_PASSWORD": "Online Identifiers",
    "_KW_COOKIE": "Online Identifiers",
    "_KW_CCTV": "Other Information",
    "_KW_VOICE": "Other Information",
    "ACCOUNT_BALANCE": "Financial Data",
    "CUSTOMER_ID": "Identity Data",
    "ACCOUNT_HOLDER_NAME": "Identity Data",
    "BRANCH_NAME": "Financial Data",
    "TRANSACTION_REFERENCE": "Financial Data",
    "TRANSACTION_HISTORY": "Financial Data",
    "TRANSACTION_AMOUNT": "Financial Data",
}


RISK_MAP: Dict[str, str] = {
    "PAN": "High",
    "AADHAAR_UNMASKED": "Critical",
    "AADHAAR_MASKED": "Medium",
    "PASSPORT": "High",
    "VOTER_ID": "Medium",
    "DRIVING_LICENCE": "Medium",
    "EMAIL": "Medium",
    "PHONE_IN": "High",
    "DATE_OF_BIRTH": "Medium",
    "_KW_PHOTOGRAPH": "Low",
    "_KW_SIGNATURE": "Low",
    "CREDIT_DEBIT_CARD": "Critical",
    "MASKED_CARD": "Medium",
    "BANK_ACCOUNT": "High",
    "IFSC": "High",
    "UPI_HANDLE": "High",
    "IP_ADDRESS": "Medium",
    "_KW_PASSWORD": "Critical",
    "_KW_COOKIE": "Medium",
    "_KW_CCTV": "Low",
    "_KW_VOICE": "Low",
    "ACCOUNT_BALANCE": "High",
    "CUSTOMER_ID": "High",
    "ACCOUNT_HOLDER_NAME": "High",
    "BRANCH_NAME": "High",
    "TRANSACTION_REFERENCE": "None",
    "TRANSACTION_HISTORY": "High",
    "TRANSACTION_AMOUNT": "High",
}


DISPLAY_NAME: Dict[str, str] = {
    "PAN": "PAN Details",
    "AADHAAR_UNMASKED": "Aadhaar Details (Unmasked)",
    "AADHAAR_MASKED": "Aadhaar Details (Masked)",
    "PASSPORT": "Passport Number",
    "VOTER_ID": "Voter ID",
    "DRIVING_LICENCE": "Driving Licence",
    "EMAIL": "Personal Email ID",
    "PHONE_IN": "Personal Phone Number",
    "DATE_OF_BIRTH": "Date of Birth",
    "_KW_PHOTOGRAPH": "Photograph Reference",
    "_KW_SIGNATURE": "Signature Reference",
    "CREDIT_DEBIT_CARD": "Credit/Debit Card Details",
    "MASKED_CARD": "Masked Card Number",
    "BANK_ACCOUNT": "Bank Account Number",
    "IFSC": "IFSC Code",
    "UPI_HANDLE": "UPI Handle",
    "IP_ADDRESS": "IP Address",
    "_KW_PASSWORD": "Password Reference",
    "_KW_COOKIE": "Cookie / Session Reference",
    "_KW_CCTV": "CCTV / Surveillance Reference",
    "_KW_VOICE": "Voice Recording Reference",
    "ACCOUNT_BALANCE": "Account Balance",
    "CUSTOMER_ID": "Customer ID",
    "ACCOUNT_HOLDER_NAME": "Account Holder Name",
    "BRANCH_NAME": "Branch Name",
    "TRANSACTION_REFERENCE": "Transaction Reference",
    "TRANSACTION_HISTORY": "Transaction History",
    "TRANSACTION_AMOUNT": "Transaction Amount",
}


def display_name(raw_type: str) -> str:
    return DISPLAY_NAME.get(raw_type, raw_type)
