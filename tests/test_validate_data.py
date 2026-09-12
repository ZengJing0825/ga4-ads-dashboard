import json
import os
import unittest

import _paths  # noqa: F401
import validate_data
from config_loader import load_yaml


class TrackingPlanCheckTest(unittest.TestCase):
    PLAN = {
        "funnels": {"creator": [{"event": "a"}, {"event": "b"}], "consumer": [{"event": "c"}]},
        "extra_events": [{"event": "d"}],
        "conversions": ["b"],
        "key_action": "e",
    }

    def test_planned_events(self):
        self.assertEqual(validate_data.planned_events(self.PLAN), {"a", "b", "c", "d", "e"})

    def test_unknown_events(self):
        data = {"ga4": {"daily_events": [{"event_name": "a"}, {"event_name": "zzz"}, {"event_name": "b"}]}}
        self.assertEqual(validate_data.unknown_events(data, self.PLAN), ["zzz"])

    def test_sample_data_has_no_unknown_events(self):
        root = _paths.ROOT_DIR
        with open(os.path.join(root, "dashboard", "data.sample.json")) as f:
            data = json.load(f)
        plan = load_yaml(os.path.join(root, "config", "tracking_plan.yaml"))
        self.assertEqual(validate_data.unknown_events(data, plan), [])

    def test_sample_validates_without_freshness(self):
        path = os.path.join(_paths.ROOT_DIR, "dashboard", "data.sample.json")
        self.assertEqual(validate_data.validate(path, check_freshness=False), [])


if __name__ == "__main__":
    unittest.main()
