import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_monetary_outcomes.py"
SPEC = importlib.util.spec_from_file_location("update_monetary_outcomes", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class OutcomeTests(unittest.TestCase):
    def test_overlap_keeps_largest_attributed_value(self):
        rows = [
            {
                "event_id": "e",
                "observed_at": "2026-01-01T00:00:00+00:00",
                "component": "valuation",
                "gross_usd": 100,
                "net_usd": -100,
                "attribution_probability": 0.5,
                "overlap_group": "g",
                "source_url": "a",
            },
            {
                "event_id": "e",
                "observed_at": "2026-01-02T00:00:00+00:00",
                "component": "valuation",
                "gross_usd": 80,
                "net_usd": -80,
                "attribution_probability": 1.0,
                "overlap_group": "g",
                "source_url": "b",
            },
        ]
        outcome = MODULE.aggregate_event(rows)
        self.assertEqual(outcome["gross_attributed_usd"], 80)
        self.assertEqual(outcome["net_attributed_usd"], -80)
        self.assertEqual(outcome["deduplicated_buckets"], 1)

    def test_different_components_are_additive(self):
        base = {
            "event_id": "e",
            "observed_at": "2026-01-01T00:00:00+00:00",
            "attribution_probability": 1.0,
            "source_url": "a",
        }
        rows = [
            {
                **base,
                "component": "real_resource",
                "gross_usd": 100,
                "net_usd": -100,
                "overlap_group": "g",
            },
            {
                **base,
                "component": "capital_allocation",
                "gross_usd": 50,
                "net_usd": 50,
                "overlap_group": "g",
            },
        ]
        outcome = MODULE.aggregate_event(rows)
        self.assertEqual(outcome["gross_attributed_usd"], 150)
        self.assertEqual(outcome["net_attributed_usd"], -50)

    def test_probability_validation(self):
        bad = {
            "event_id": "e",
            "observed_at": "x",
            "component": "x",
            "gross_usd": 1,
            "attribution_probability": 2,
            "overlap_group": "g",
            "source_url": "u",
        }
        with self.assertRaises(ValueError):
            MODULE.validate(bad)


if __name__ == "__main__":
    unittest.main()
