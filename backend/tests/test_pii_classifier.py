import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from aadhaar_validator import verhoeff_is_valid  # noqa: E402
from candidate_generator import generate_entity_candidates  # noqa: E402
from entity_resolution import resolve_entities  # noqa: E402
from layout_mapping import build_layout_debug  # noqa: E402
from ocr_structure import parse_ocr_structure  # noqa: E402
from pii_classifier import detect_pii_in_blocks  # noqa: E402


def _block(text, x1, y1, x2, y2, confidence=0.96):
    return {
        "text": text,
        "confidence": confidence,
        "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
    }


class BankingPiiClassifierTests(unittest.TestCase):
    def _account_summary_blocks(self):
        return [
            _block("Statement of Account", 22, 248, 188, 268),
            _block("Account Number", 22, 288, 130, 304),
            _block("Customer ID", 578, 284, 666, 300),
            _block("SANOJ", 22, 314, 74, 332),
            _block("NIXON", 82, 314, 138, 332),
            _block("A51721096", 578, 310, 666, 328),
            _block("0587053000016422", 22, 340, 202, 360),
            _block("Branch Name", 22, 378, 118, 396),
            _block("IFSC Code", 578, 378, 658, 396),
            _block("RAJAGIRI", 22, 408, 105, 426),
            _block("VALLEY,", 112, 408, 178, 426),
            _block("KAKKANAD", 186, 408, 276, 426),
            _block("SIBL0000587", 578, 408, 694, 426),
            _block("Account Balance", 22, 476, 146, 494),
            _block("Available Balance", 578, 476, 720, 494),
            _block("Rs 79.74", 22, 504, 92, 524),
            _block("Rs 79.74", 578, 504, 648, 524),
            _block("Mini Statement", 492, 640, 620, 664),
            _block("12-May-26", 22, 742, 102, 762),
            _block("UPI/SIBL/649844712639/SIB STAFF CO-O...", 22, 770, 390, 790),
            _block("-Rs 17", 1030, 770, 1078, 790),
            _block("11-May-26", 22, 850, 102, 870),
            _block("UPI/UBIN/649745822146/SHAUN C L/UPI", 22, 878, 380, 898),
            _block("+ Rs 66", 1018, 878, 1078, 898),
            _block("09-May-26", 22, 970, 102, 990),
            _block("UPI/SIBL/612972952283/SANOJ NIXON/...", 22, 998, 390, 1018),
            _block("-Rs 3,599", 998, 998, 1078, 1018),
        ]

    def test_layout_mapping_separates_customer_id_from_account_holder_name(self):
        blocks = self._account_summary_blocks()

        entities = detect_pii_in_blocks(blocks)
        by_type = {}
        for entity in entities:
            by_type.setdefault(entity["raw_type"], []).append(entity)

        self.assertEqual("A51721096", by_type["CUSTOMER_ID"][0]["value"])
        self.assertEqual("SANOJ NIXON", by_type["ACCOUNT_HOLDER_NAME"][0]["value"])
        self.assertEqual("0587053000016422", by_type["BANK_ACCOUNT"][0]["value"])
        self.assertEqual("SIBL0000587", by_type["IFSC"][0]["value"])
        self.assertEqual("RAJAGIRI VALLEY, KAKKANAD", by_type["BRANCH_NAME"][0]["value"])
        self.assertTrue(any(entity["value"] == "79.74" for entity in by_type["ACCOUNT_BALANCE"]))
        self.assertTrue(any(entity["raw_type"] == "TRANSACTION_HISTORY" for entity in entities))
        self.assertFalse(
            any(
                entity["raw_type"] == "CUSTOMER_ID" and entity["value"] in {"SANOJ", "SANOJ NIXON"}
                for entity in entities
            )
        )
        self.assertEqual("LayoutMapping", by_type["CUSTOMER_ID"][0]["source_rule"])
        self.assertIn("spatial_confidence", by_type["CUSTOMER_ID"][0])
        self.assertGreaterEqual(by_type["CUSTOMER_ID"][0]["confidence"], 0.85)

    def test_ocr_structure_exposes_rows_columns_and_cells(self):
        structure = parse_ocr_structure(self._account_summary_blocks())

        self.assertGreaterEqual(len(structure["rows"]), 8)
        self.assertGreaterEqual(len(structure["columns"]), 2)
        customer_row = next(row for row in structure["rows"] if "Customer ID" in row["text"])
        self.assertTrue(any(cell["text"] == "Customer ID" for cell in customer_row["cells"]))
        self.assertTrue(all("x1" in cell and "column_index" in cell for cell in customer_row["cells"]))

    def test_layout_debug_returns_candidates_and_rejection_reasons(self):
        blocks = self._account_summary_blocks()
        structure = parse_ocr_structure(blocks)
        debug = build_layout_debug(blocks, structure, "Bank Statement")

        customer_decision = next(item for item in debug["decisions"] if item["entity_type"] == "CUSTOMER_ID")
        self.assertEqual("A51721096", customer_decision["selected"]["value"])
        self.assertGreater(customer_decision["candidate_count"], 1)
        rejected_names = [
            candidate for candidate in customer_decision["candidates"]
            if candidate["candidate_text"] in {"SANOJ", "SANOJ NIXON"}
        ]
        self.assertTrue(rejected_names)
        self.assertTrue(all(not candidate["accepted"] for candidate in rejected_names))

    def test_candidate_generation_does_not_make_regex_final_truth(self):
        blocks = [
            _block("09-May-26", 10, 10, 90, 30),
            _block("UPI/SIBL/234567890124/SANOJ NIXON/", 10, 40, 360, 60),
            _block("-Rs 3599", 450, 40, 520, 60),
        ]
        structure = parse_ocr_structure(blocks)
        payload = generate_entity_candidates(blocks, structure, "Bank Statement")
        candidate = next(item for item in payload["candidates"] if item["value"] == "234567890124")
        candidate_types = {item["type"]: item["confidence"] for item in candidate["candidate_types"]}

        self.assertIn("AADHAAR_UNMASKED", candidate_types)
        self.assertIn("TRANSACTION_REFERENCE", candidate_types)
        self.assertGreater(candidate_types["TRANSACTION_REFERENCE"], candidate_types["AADHAAR_UNMASKED"])

    def test_resolver_uses_ai_semantics_to_override_ambiguous_regex(self):
        blocks = [
            _block("09-May-26", 10, 10, 90, 30),
            _block("UPI/SIBL/234567890124/SANOJ NIXON/", 10, 40, 360, 60),
            _block("-Rs 3599", 450, 40, 520, 60),
        ]
        structure = parse_ocr_structure(blocks)
        payload = generate_entity_candidates(blocks, structure, "Bank Statement")
        ai_resolution = {
            "status": "success",
            "entity_classifications": [
                {
                    "value": "234567890124",
                    "final_type": "TRANSACTION_REFERENCE",
                    "confidence": 0.93,
                    "reasoning": "Value appears inside a UPI transaction row, not an Aadhaar field.",
                    "supporting_evidence": ["UPI/SIBL/... transaction narration"],
                    "rejected_candidates": [{"type": "AADHAAR_UNMASKED", "reason": "No Aadhaar label/context."}],
                }
            ],
        }
        entities = resolve_entities(payload, ai_resolution)
        ref = next(entity for entity in entities if entity["value"] == "234567890124")

        self.assertEqual("TRANSACTION_REFERENCE", ref["raw_type"])
        self.assertEqual("HybridAIResolution", ref["source_rule"])
        self.assertFalse(any(entity["raw_type"] == "AADHAAR_UNMASKED" for entity in entities))

    def test_statement_references_stay_transaction_references(self):
        blocks = [
            _block("Account Number", 10, 10, 120, 30),
            _block("0587053000016422", 10, 34, 200, 54),
            _block("12-May-26", 10, 120, 90, 140),
            _block("UPI/SIBL/", 10, 148, 95, 168),
            _block("649844712639", 97, 148, 200, 168),
            _block("/SIB STAFF CO-O...", 202, 148, 360, 168),
            _block("-₹ 17", 450, 148, 500, 168),
            _block("08-May-26", 10, 270, 90, 290),
            _block("UPI/SIBL/612846027773/SHON", 10, 298, 250, 318),
            _block("SABU/UPI", 252, 298, 340, 318),
            _block("-₹ 165", 450, 298, 520, 318),
        ]

        entities = detect_pii_in_blocks(blocks)
        refs = {entity["value"]: entity for entity in entities if entity["raw_type"] == "TRANSACTION_REFERENCE"}

        self.assertIn("649844712639", refs)
        self.assertIn("612846027773", refs)
        self.assertNotIn(
            "649844712639",
            {entity["value"] for entity in entities if entity["raw_type"] == "AADHAAR_UNMASKED"},
        )
        self.assertEqual(
            "BANK_ACCOUNT",
            next(entity["raw_type"] for entity in entities if entity["value"] == "0587053000016422"),
        )

    def test_split_upi_row_keeps_no_space_transaction_chain(self):
        blocks = [
            _block("11-May-26", 10, 10, 90, 30),
            _block("UPI", 10, 36, 40, 56),
            _block("/", 41, 36, 46, 56),
            _block("UBIN", 47, 36, 85, 56),
            _block("/", 86, 36, 91, 56),
            _block("649745822146", 92, 36, 200, 56),
            _block("/", 201, 36, 206, 56),
            _block("SHAUN C L", 207, 36, 300, 56),
            _block("/UPI", 301, 36, 340, 56),
        ]

        entities = detect_pii_in_blocks(blocks)
        ref = next(entity for entity in entities if entity["value"] == "649745822146")
        self.assertEqual("TRANSACTION_REFERENCE", ref["raw_type"])
        self.assertIn("UBIN", ref["ocr_context"])

    def test_valid_aadhaar_requires_positive_aadhaar_context(self):
        aadhaar_value = "234567890124"
        self.assertTrue(verhoeff_is_valid(aadhaar_value))
        blocks = [
            _block("Aadhaar Number", 10, 10, 140, 30),
            _block(aadhaar_value, 150, 10, 270, 30),
        ]

        entities = detect_pii_in_blocks(blocks)
        aadhaar = next(entity for entity in entities if entity["value"] == aadhaar_value)
        self.assertEqual("AADHAAR_UNMASKED", aadhaar["raw_type"])
        self.assertTrue(aadhaar["aadhaar_checksum_valid"])

    def test_checksum_valid_value_in_transaction_row_is_not_aadhaar(self):
        aadhaar_value = "234567890124"
        blocks = [
            _block("09-May-26", 10, 10, 90, 30),
            _block("UPI/SIBL/" + aadhaar_value + "/SANOJ NIXON/", 10, 40, 360, 60),
            _block("-₹ 3599", 450, 40, 520, 60),
        ]

        entities = detect_pii_in_blocks(blocks)
        ref = next(entity for entity in entities if entity["value"] == aadhaar_value)
        self.assertEqual("TRANSACTION_REFERENCE", ref["raw_type"])
        self.assertFalse(any(entity["raw_type"] == "AADHAAR_UNMASKED" for entity in entities))

    def test_bare_12_digit_value_stays_unclassified(self):
        blocks = [_block("649844712639", 10, 10, 140, 30)]
        entities = detect_pii_in_blocks(blocks)
        self.assertFalse(any(entity["value"] == "649844712639" for entity in entities))


if __name__ == "__main__":
    unittest.main()
