import unittest
from pathlib import Path

import yaml

from scripts import monitor


ROOT = Path(__file__).resolve().parents[1]


class MonitorScoringTests(unittest.TestCase):
    def test_source_keywords_do_not_double_count_global_terms(self):
        keywords_config = {
            "keywords": [
                {"term": "AI", "aliases": ["AI", "artificial intelligence"], "weight": 5},
                {"term": "Security", "aliases": ["security", "cybersecurity"], "weight": 6},
            ]
        }
        source = {"keywords": ["AI", "security", "new narrow signal"]}

        specs = monitor.keyword_specs(keywords_config, source)
        terms = [spec["term"] for spec in specs]

        self.assertEqual(terms.count("AI"), 1)
        self.assertEqual(terms.count("Security"), 1)
        self.assertIn("new narrow signal", terms)

    def test_mixed_classification_uses_default_mixed_action(self):
        finding = monitor.Finding(
            title="AI exploit with workflow gap",
            url="",
            source="Unit Test",
            source_type="manual_note",
            published_at=None,
            fetched_at="2026-01-01T00:00:00+00:00",
            summary="",
        )
        keywords_config = {"keywords": [{"term": "AI", "aliases": ["AI"], "weight": 1}]}
        rules = {
            "scoring": {"high_threshold": 999, "max_score": 100},
            "classification": {
                "risk_terms": ["exploit"],
                "opportunity_terms": ["workflow gap"],
            },
            "actions": {
                "default_mixed": "Mixed action",
                "default_risk": "Risk action",
                "default_opportunity": "Opportunity action",
                "default_observation": "Observation action",
            },
        }

        scored = monitor.score_finding(finding, {}, keywords_config, rules)

        self.assertEqual(scored.risk_or_opportunity, "mixed")
        self.assertEqual(scored.recommended_action, "Mixed action")

    def test_briefing_limits_items_per_source_per_section(self):
        def finding(title: str, source: str, score: int) -> monitor.Finding:
            return monitor.Finding(
                title=title,
                url="",
                source=source,
                source_type="rss",
                published_at=None,
                fetched_at="2026-01-01T00:00:00+00:00",
                summary="",
                relevance_score=score,
            )

        rules = {
            "scoring": {
                "high_threshold": 24,
                "medium_threshold": 12,
                "observe_threshold": 1,
            },
            "briefing": {
                "max_items_per_section": 3,
                "max_items_per_source_per_section": 1,
            },
        }

        markdown = monitor.render_briefing_md(
            [
                finding("A strongest", "Source A", 40),
                finding("A second", "Source A", 39),
                finding("A third", "Source A", 38),
                finding("B strongest", "Source B", 37),
            ],
            [],
            rules,
        )

        self.assertIn("A strongest", markdown)
        self.assertNotIn("A second", markdown)
        self.assertNotIn("A third", markdown)
        self.assertIn("B strongest", markdown)
        self.assertEqual(markdown.count("- Quelle: Source A"), 1)
        self.assertEqual(markdown.count("- Quelle: Source B"), 1)


class MonitorConfigTests(unittest.TestCase):
    def test_rules_yaml_exposes_mixed_action_and_source_render_limit(self):
        rules = yaml.safe_load((ROOT / "config" / "rules.yaml").read_text(encoding="utf-8"))

        self.assertIn("default_mixed", rules["actions"])
        self.assertGreaterEqual(rules["scoring"]["high_threshold"], 24)
        self.assertGreaterEqual(rules["scoring"]["medium_threshold"], 12)
        self.assertGreaterEqual(rules["briefing"]["max_items_per_source_per_section"], 1)


if __name__ == "__main__":
    unittest.main()
