import unittest

import _paths  # noqa: F401
from taxonomy import Taxonomy, summarize_by

CONFIG = {
    "landing_type": [
        {"pattern": r"\bpmax\b", "value": "pmax"},
        {"pattern": r"\busecase\b", "value": "usecase_page"},
        {"pattern": r"\bsingle\b", "value": "single_page"},
        {"pattern": r"\bskill\b", "value": "skill_page"},
        {"pattern": r"\bhome\b|\bbrand\b", "value": "homepage"},
    ],
    "use_case": [
        {"pattern": r"trading", "value": "trading"},
        {"pattern": r"quant", "value": "quant"},
        {"pattern": r"\ball\b", "value": "all"},
    ],
    "defaults": {"landing_type": "unknown", "use_case": "unknown"},
}


class TaxonomyParseTest(unittest.TestCase):
    def setUp(self):
        self.tax = Taxonomy(CONFIG)

    def test_parses_both_dimensions(self):
        self.assertEqual(self.tax.parse("search-usecase-trading-us"),
                         {"landing_type": "usecase_page", "use_case": "trading"})
        self.assertEqual(self.tax.parse("pmax-all-us"),
                         {"landing_type": "pmax", "use_case": "all"})

    def test_case_insensitive(self):
        self.assertEqual(self.tax.classify("PMAX-ALL-US", "landing_type"), "pmax")

    def test_first_match_wins(self):
        # 'single' is listed before 'skill'; both words present -> single_page
        self.assertEqual(self.tax.classify("single skill page", "landing_type"), "single_page")

    def test_defaults_when_nothing_matches(self):
        self.assertEqual(self.tax.parse("display-retargeting"),
                         {"landing_type": "unknown", "use_case": "unknown"})

    def test_word_boundaries(self):
        self.assertEqual(self.tax.classify("homework-x", "landing_type"), "unknown")
        self.assertEqual(self.tax.classify("search-home-x", "landing_type"), "homepage")

    def test_tag_rows_in_place(self):
        rows = [{"campaign_name": "search-single-quant-us"}]
        self.tax.tag_rows(rows)
        self.assertEqual(rows[0]["landing_type"], "single_page")
        self.assertEqual(rows[0]["use_case"], "quant")

    def test_shipped_config_loads_and_covers_sample_names(self):
        tax = Taxonomy.load()
        self.assertEqual(tax.classify("search-usecase-research-global", "landing_type"), "usecase_page")
        self.assertEqual(tax.classify("search-skill-quant-global", "landing_type"), "skill_page")
        self.assertEqual(tax.classify("search-home-brand-us", "use_case"), "brand")


class SummarizeByTest(unittest.TestCase):
    ROWS = [
        {"campaign_name": "a", "landing_type": "usecase_page", "impressions": 1000, "clicks": 45, "cost": 50.0, "conversions": 6.0},
        {"campaign_name": "a", "landing_type": "usecase_page", "impressions": 1000, "clicks": 45, "cost": 50.0, "conversions": 6.5},
        {"campaign_name": "b", "landing_type": "pmax", "impressions": 5000, "clicks": 95, "cost": 80.0, "conversions": 4.0},
        {"campaign_name": "c", "landing_type": "pmax", "impressions": 5000, "clicks": 95, "cost": 80.0, "conversions": 0.0},
    ]

    def test_aggregates_and_rates(self):
        out = {b["landing_type"]: b for b in summarize_by(self.ROWS, "landing_type")}
        uc, pm = out["usecase_page"], out["pmax"]
        self.assertEqual(uc["campaign_count"], 1)
        self.assertEqual(uc["clicks"], 90)
        self.assertEqual(uc["cost"], 100.0)
        self.assertEqual(uc["conversions"], 12.5)
        self.assertEqual(uc["ctr"], 4.5)
        self.assertEqual(uc["cvr"], 13.89)
        self.assertEqual(uc["cpa"], 8.0)
        self.assertEqual(pm["campaign_count"], 2)
        self.assertEqual(pm["ctr"], 1.9)
        self.assertEqual(pm["cpa"], 40.0)

    def test_sorted_by_cost_desc(self):
        out = summarize_by(self.ROWS, "landing_type")
        self.assertEqual([b["landing_type"] for b in out], ["pmax", "usecase_page"])

    def test_missing_dimension_goes_to_unknown(self):
        out = summarize_by([{"campaign_name": "x", "clicks": 1, "impressions": 10, "cost": 1.0, "conversions": 0}], "use_case")
        self.assertEqual(out[0]["use_case"], "unknown")
        self.assertIsNone(out[0]["cpa"])


if __name__ == "__main__":
    unittest.main()
