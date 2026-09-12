import unittest

import _paths  # noqa: F401
import experiments

ROWS = [
    {"date": "2026-09-01", "campaign_name": "a", "cost": 100.0, "clicks": 90, "impressions": 2000, "conversions": 12.0},
    {"date": "2026-09-02", "campaign_name": "a", "cost": 100.0, "clicks": 90, "impressions": 2000, "conversions": 13.0},
    {"date": "2026-09-03", "campaign_name": "a", "cost": 100.0, "clicks": 90, "impressions": 2000, "conversions": 11.0},  # outside window
    {"date": "2026-09-01", "campaign_name": "b", "cost": 50.0, "clicks": 20, "impressions": 2000, "conversions": 1.0},
    {"date": "2026-09-02", "campaign_name": "z", "cost": 999.0, "clicks": 1, "impressions": 1, "conversions": 0.0},  # not covered
]


def exp(**kw):
    base = {"id": "EXP-T", "date": "2026-09-01", "end_date": "2026-09-02", "landing_type": "usecase_page",
            "campaigns": ["a", "b"], "status": "running",
            "kill_rule": {"metric": "cpa", "above": 12, "min_spend": 100},
            "scale_rule": {"metric": "cpa", "below": 10, "min_conversions": 20}}
    base.update(kw)
    return base


class JoinTest(unittest.TestCase):
    def test_join_respects_campaigns_and_window(self):
        j = experiments.join_experiment(exp(), ROWS)
        self.assertEqual(j["days"], 2)
        self.assertEqual(j["cost"], 250.0)
        self.assertEqual(j["clicks"], 200)
        self.assertEqual(j["conversions"], 26.0)
        self.assertEqual(j["ctr"], 3.33)     # 200 / 6000
        self.assertEqual(j["cvr"], 13.0)
        self.assertEqual(j["cpa"], 9.62)
        self.assertEqual(j["verdict"], "SCALE")

    def test_open_end_date_includes_everything_after_start(self):
        j = experiments.join_experiment(exp(end_date=None, campaigns=["a"]), ROWS)
        self.assertEqual(j["days"], 3)
        self.assertEqual(j["cost"], 300.0)

    def test_verdicts(self):
        self.assertEqual(experiments.evaluate_rules(exp(cost=50.0, clicks=10, conversions=2.0, cpa=25.0)), "LEARNING")
        self.assertEqual(experiments.evaluate_rules(exp(cost=500.0, clicks=400, conversions=25.0, cpa=20.0)), "KILL")
        self.assertEqual(experiments.evaluate_rules(exp(cost=500.0, clicks=400, conversions=0.0, cpa=None)), "KILL")
        self.assertEqual(experiments.evaluate_rules(exp(cost=500.0, clicks=400, conversions=10.0, cpa=11.0)), "HOLD")
        self.assertEqual(experiments.evaluate_rules(exp(cost=500.0, clicks=400, conversions=60.0, cpa=8.0)), "SCALE")
        self.assertEqual(experiments.evaluate_rules(exp(cost=500.0, clicks=400, conversions=60.0, cpa=11.0)), "HOLD")

    def test_uncovered_campaigns(self):
        self.assertEqual(experiments.uncovered_campaigns([exp()], ROWS), ["z"])

    def test_shipped_config_joins_sample_data(self):
        import json
        import os
        exps = experiments.load_experiments()
        self.assertTrue(3 <= len(exps) <= 5)
        for e in exps:
            self.assertRegex(e["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertIn(e["landing_type"], ("homepage", "skill_page", "usecase_page", "single_page", "pmax"))
            self.assertIn(e["status"], experiments.STATUSES)
            for key in ("hypothesis", "campaigns", "daily_budget", "conversion_event", "kill_rule", "scale_rule", "conclusion"):
                self.assertIn(key, e, "%s missing %s" % (e["id"], key))
        with open(os.path.join(_paths.ROOT_DIR, "dashboard", "data.sample.json")) as f:
            rows = json.load(f)["ads"]["campaign_daily"]
        joined = {j["id"]: j for j in experiments.join_all(exps, rows)}
        self.assertTrue(all(j["days"] > 0 for j in joined.values()))
        by_type = {j["landing_type"]: j["cpa"] for j in joined.values()}
        self.assertTrue(7 <= by_type["usecase_page"] <= 9)
        self.assertTrue(19 <= by_type["pmax"] <= 21)
        self.assertTrue(by_type["usecase_page"] < by_type["single_page"] < by_type["pmax"])


if __name__ == "__main__":
    unittest.main()
