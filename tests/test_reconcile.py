import os
import tempfile
import unittest

import _paths  # noqa: F401
import reconcile


class GapMathTest(unittest.TestCase):
    def test_gap_pct_sign_and_rounding(self):
        self.assertEqual(reconcile.gap_pct(88, 100), -12.0)
        self.assertEqual(reconcile.gap_pct(105, 100), 5.0)
        self.assertEqual(reconcile.gap_pct(1, 3), -66.67)
        self.assertIsNone(reconcile.gap_pct(5, 0))

    def test_compare_uses_intersection_and_totals(self):
        ga4 = {"2026-09-01": 90, "2026-09-02": 85, "2026-09-03": 40}
        export = {"2026-09-01": 100, "2026-09-02": 100, "2026-09-04": 10}
        rows, totals = reconcile.compare(ga4, export)
        self.assertEqual([r["date"] for r in rows], ["2026-09-01", "2026-09-02"])
        self.assertEqual(rows[0]["gap_pct"], -10.0)
        self.assertEqual(totals["ga4"], 175)
        self.assertEqual(totals["export"], 200)
        self.assertEqual(totals["gap_pct"], -12.5)
        self.assertEqual(totals["only_in_ga4"], ["2026-09-03"])
        self.assertEqual(totals["only_in_export"], ["2026-09-04"])

    def test_threshold(self):
        self.assertTrue(reconcile.exceeds({"gap_pct": -12.5}, 10))
        self.assertFalse(reconcile.exceeds({"gap_pct": -9.9}, 10))
        self.assertTrue(reconcile.exceeds({"gap_pct": 11.0}, 10))
        self.assertFalse(reconcile.exceeds({"gap_pct": None}, 10))


class IoTest(unittest.TestCase):
    def test_ga4_daily_counts_filters_event_and_window(self):
        data = {"ga4": {"daily_events": [
            {"date": "2026-09-01", "event_name": "signup", "event_count": 10},
            {"date": "2026-09-01", "event_name": "signup", "event_count": 5},
            {"date": "2026-09-02", "event_name": "signup", "event_count": 7},
            {"date": "2026-09-02", "event_name": "login", "event_count": 99},
        ]}}
        self.assertEqual(reconcile.ga4_daily_counts(data, "signup"), {"2026-09-01": 15, "2026-09-02": 7})
        self.assertEqual(reconcile.ga4_daily_counts(data, "signup", start="2026-09-02"), {"2026-09-02": 7})

    def test_read_export_with_and_without_event_column(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(path, "w") as f:
                f.write("Date,Event_Name,Count\n2026-09-01,signup,12\n2026-09-01,login,50\n2026-09-02,signup,8\n")
            self.assertEqual(reconcile.read_export(path, "signup"), {"2026-09-01": 12, "2026-09-02": 8})
            with open(path, "w") as f:
                f.write("date,count\n2026-09-01,12\n2026-09-02,8\n")
            self.assertEqual(reconcile.read_export(path, "signup", end="2026-09-01"), {"2026-09-01": 12})
        finally:
            os.remove(path)

    def test_shipped_example_shows_gap_above_threshold(self):
        import json
        root = _paths.ROOT_DIR
        with open(os.path.join(root, "dashboard", "data.sample.json")) as f:
            data = json.load(f)
        ga4 = reconcile.ga4_daily_counts(data, "signup")
        export = reconcile.read_export(os.path.join(root, "examples", "first_party_signups.csv"), "signup")
        _, totals = reconcile.compare(ga4, export)
        self.assertEqual(totals["days"], 30)
        self.assertTrue(-16 < totals["gap_pct"] < -10)


if __name__ == "__main__":
    unittest.main()
