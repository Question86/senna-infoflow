import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "economic_weight_layer.py"
SPEC = importlib.util.spec_from_file_location("economic_weight_layer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

CONFIG = {
    "priors": {
        "default": {"p10": 100_000, "p50": 10_000_000, "p90": 1_000_000_000},
        "by_event_class": {
            "vulnerability": {"p10": 250_000, "p50": 25_000_000, "p90": 2_500_000_000},
            "natural_disaster": {"p10": 1_000_000, "p50": 100_000_000, "p90": 10_000_000_000},
        },
    }
}

class EconomicWeightLayerTests(unittest.TestCase):
    def test_stable_event_id_uses_cluster_key(self):
        first = {"key": "title:test", "title": "A"}
        second = {"key": "title:test", "title": "Changed title"}
        self.assertEqual(MODULE.stable_event_id(first), MODULE.stable_event_id(second))

    def test_classifies_earthquake_and_infrastructure(self):
        cluster = {
            "key": "title:quake",
            "title": "Earthquake disrupts port infrastructure",
            "sources": ["USGS", "GDACS"],
            "source_classes": ["tier1_primary"],
            "urls": ["https://example.test/quake"],
            "finding_count": 2,
            "max_score": 15,
            "credibility_total": 4.0,
            "cross_source_confirmed": True,
            "momentum_delta": 2,
            "network_score": 22.0,
            "watchgraph_modules": ["climate_disaster_infrastructure"],
        }
        result = MODULE.build_observation(cluster, CONFIG, "2026-07-23T00:00:00+00:00")
        self.assertIn("natural_disaster", result["features"]["event_classes"])
        self.assertIn("infrastructure", result["features"]["capital_channels"])
        self.assertGreater(result["forecast"]["lifetime_monetary_weight_usd"]["p50"], 100_000_000)

    def test_initial_forecast_is_immutable(self):
        cluster = {
            "key": "title:cve-test",
            "title": "Critical CVE-2026-0001 vulnerability",
            "sources": ["CERT"],
            "finding_count": 1,
            "max_score": 9,
            "credibility_total": 1.5,
            "cross_source_confirmed": False,
            "momentum_delta": 1,
            "network_score": 10.0,
            "watchgraph_modules": [],
        }
        record = MODULE.build_observation(cluster, CONFIG, "2026-07-23T00:00:00+00:00")
        initial = dict(record["forecast"])
        later = dict(cluster)
        later["sources"] = ["CERT", "CISA", "Vendor"]
        later["momentum_delta"] = 5
        later["network_score"] = 40
        MODULE.update_record(record, later, "2026-07-24T00:00:00+00:00")
        self.assertEqual(record["forecast"], initial)
        self.assertEqual(len(record["observations"]), 2)

    def test_signal_multiplier_is_bounded(self):
        cluster = {
            "sources": [f"s{i}" for i in range(50)],
            "momentum_delta": 100,
            "max_score": 500,
            "cross_source_confirmed": True,
        }
        self.assertLessEqual(MODULE.signal_multiplier(cluster), 1.85)

if __name__ == "__main__":
    unittest.main()
