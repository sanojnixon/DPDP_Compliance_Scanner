"""
Live HF inference test — calls AI model with a minimal banking payload.
Run from backend/ directory.
"""
import sys, os, json, time
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from services.ai_service import run_text_analysis

print("=== DPDP AI Service — Live HF Inference Test ===")
print(f"Model : {os.getenv('HF_TEXT_MODEL', 'AI_MODEL')}")
print(f"Token : {os.getenv('HF_API_KEY', '')[:12]}...")
print()

t0 = time.monotonic()
result = run_text_analysis(
    document_type="Bank Statement",
    ocr={
        "total_blocks": 8,
        "avg_confidence": 0.91,
        "full_text": (
            "South Indian Bank\n"
            "Account Summary\n"
            "Account Holder: SANOJ NIXON\n"
            "Account No: XXXX XXXX 4892\n"
            "Available Balance: Rs. 52,340.00\n"
            "Transaction History\n"
            "Date       Description         Amount\n"
            "14-05-2026 UPI/649844712639     -500.00\n"
            "13-05-2026 NEFT/612972952283    +2000.00\n"
        ),
    },
    entities=[
        {"type": "Account Holder Name", "raw_type": "ACCOUNT_HOLDER_NAME",
         "category": "Identity Data", "risk": "High", "masked": False,
         "confidence": 0.97, "value": "SANOJ NIXON"},
        {"type": "Account Balance", "raw_type": "ACCOUNT_BALANCE",
         "category": "Financial Data", "risk": "High", "masked": False,
         "confidence": 0.94, "value": "52340.00"},
        {"type": "Transaction Reference", "raw_type": "TRANSACTION_REFERENCE",
         "category": "Financial Data", "risk": "None", "masked": False,
         "confidence": 0.95, "value": "649844712639",
         "reason": "12-digit UPI reference suppressed from Aadhaar match"},
    ],
    compliance={
        "score": 55,
        "grade": "C",
        "by_risk": {"Critical": 0, "High": 2, "Medium": 0, "Low": 0},
        "flags": [
            "ℹ DPDP Guidance: Account balance detected. Financial data requires strict access controls.",
        ],
    },
    metadata={"filename": "bank_statement_test.png"},
)

latency = time.monotonic() - t0
print(f"Status  : {result.get('status')}")
print(f"Latency : {latency:.1f}s")
print(f"Model   : {result.get('model')}")
print(f"Risk    : {result.get('overall_risk')}")
print(f"Summary : {result.get('ai_summary', '')[:200]}")
print(f"Findings: {len(result.get('findings', []))}")
for f in result.get('findings', [])[:3]:
    print(f"  [{f['severity']}] {f['issue']}")
print(f"Recs    : {result.get('recommendations', [])[:2]}")
print()
print("Full result JSON:")
print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
