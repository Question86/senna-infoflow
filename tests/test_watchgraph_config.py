import pathlib
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WatchgraphConfigTests(unittest.TestCase):
    def test_watchgraph_has_twenty_modules(self):
        data = yaml.safe_load((ROOT / "config" / "watchgraph.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(data["modules"]), 20)

    def test_required_regions_exist(self):
        data = yaml.safe_load((ROOT / "config" / "watchgraph.yaml").read_text(encoding="utf-8"))
        regions = set(data["regions"])
        required = {
            "europe",
            "usa",
            "india",
            "south_america",
            "canada",
            "japan",
            "south_korea",
            "australia",
            "southeast_asia",
            "china_credible_only",
        }
        self.assertTrue(required.issubset(regions))

    def test_active_global_sources_are_rss_compatible(self):
        data = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
        active_global = [
            source
            for source in data["sources"]
            if source["id"].startswith(("usgs_", "gdacs_", "nhc_"))
        ]
        self.assertGreaterEqual(len(active_global), 5)
        self.assertTrue(all(source["enabled"] for source in active_global))
        self.assertTrue(all(source["type"] == "rss" for source in active_global))


if __name__ == "__main__":
    unittest.main()
