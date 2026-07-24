import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_economic_evidence_candidates.py"
SPEC = importlib.util.spec_from_file_location("extract_economic_evidence_candidates", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class EvidenceCandidateTests(unittest.TestCase):
    def test_extracts_usd_amount_with_context(self):
        text = "The company reported $1.5 billion in expected costs after the outage."
        rows = MODULE.extract_from_text("evt_test", "https://example.gov/report", text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["currency"], "USD")
        self.assertEqual(rows[0]["amount_native"], 1.5e9)
        self.assertIsNone(rows[0]["attribution_probability"])
        self.assertEqual(rows[0]["review_status"], "pending")

    def test_euro_stays_pending_fx(self):
        rows = MODULE.extract_from_text("evt_test", "https://example.eu/report", "Budget: €50 million.")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount_native"], 50e6)
        self.assertIsNone(rows[0]["amount_usd"])
        self.assertEqual(rows[0]["conversion_status"], "pending_fx")

    def test_candidate_id_is_stable(self):
        text = "The filing said $25 million in revenue."
        first = MODULE.extract_from_text("evt_test", "https://example.com/a", text)[0]
        second = MODULE.extract_from_text("evt_test", "https://example.com/a", text)[0]
        self.assertEqual(first["candidate_id"], second["candidate_id"])

if __name__ == "__main__":
    unittest.main()
