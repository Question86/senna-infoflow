import pathlib
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]


class NetworkHubConfigTests(unittest.TestCase):
    def test_network_hub_contains_all_feedback_items(self):
        data = yaml.safe_load((ROOT / "config" / "network_hub.yaml").read_text(encoding="utf-8"))
        items = [item for tier in data["tiers"] for item in tier["items"]]
        self.assertEqual(len(items), 20)

    def test_network_hub_defines_three_cadences(self):
        data = yaml.safe_load((ROOT / "config" / "network_hub.yaml").read_text(encoding="utf-8"))
        self.assertIn("hot", data["schedules"])
        self.assertIn("medium", data["schedules"])
        self.assertIn("background", data["schedules"])

    def test_source_credibility_has_social_and_repo_demotions(self):
        data = yaml.safe_load((ROOT / "config" / "source_credibility.yaml").read_text(encoding="utf-8"))
        self.assertLess(data["classes"]["tier4_platform_social"]["weight"], 1.0)
        self.assertLess(data["classes"]["tier5_generic_repo"]["weight"], 1.0)
        self.assertTrue(data["rules"]["single_github_repo_high_cap"])
        self.assertTrue(data["rules"]["social_requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
