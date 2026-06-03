import sys
sys.path.insert(0, '.')
from services.ai_service import run_text_analysis, HF_TEXT_MODEL, _build_yaml_payload, _parse_json_response
print('Import OK')
print('Model:', HF_TEXT_MODEL)

# YAML build smoke test
yaml_out = _build_yaml_payload(
    document_type='Bank Statement',
    ocr={'total_blocks': 5, 'avg_confidence': 0.92,
         'full_text': 'Account Balance 5000\nTransaction 649844712639'},
    entities=[{
        'type': 'Transaction Reference',
        'raw_type': 'TRANSACTION_REFERENCE',
        'category': 'Financial Data',
        'risk': 'None',
        'value': '649844712639',
        'confidence': 0.95,
    }],
    compliance={'score': 70, 'grade': 'C', 'by_risk': {'High': 1}, 'flags': []},
    metadata={'filename': 'test.png'},
)
print('YAML payload chars:', len(yaml_out))
print(yaml_out[:400])

# JSON parse test (including AI model think-tag stripping)
sample = (
    '<think>some reasoning</think>\n'
    '{"document_type":"Bank Statement","ai_summary":"Test","overall_risk":"High",'
    '"screen_sensitivity":"High","purpose_limitation":{"assessment":"ok",'
    '"excessive_data_exposure":false},"findings":[],"recommendations":[],'
    '"observations":[],"limitations":[]}'
)
result = _parse_json_response(sample)
print('Parse OK: overall_risk =', result['overall_risk'])
