import unittest

import _paths  # noqa: F401
import kpi


class KpiMathTest(unittest.TestCase):
    def test_ctr_cvr_percent(self):
        self.assertEqual(kpi.ctr(45, 1000), 4.5)
        self.assertEqual(kpi.cvr(7, 100), 7.0)
        self.assertEqual(kpi.cvr(1, 3), 33.33)

    def test_cpc_cpa(self):
        self.assertEqual(kpi.cpc(110.0, 100), 1.1)
        self.assertEqual(kpi.cpa(20595.36, 1308), 15.75)
        self.assertEqual(kpi.cpa(100.0, 12.5), 8.0)

    def test_activation_rate(self):
        self.assertEqual(kpi.activation_rate(649, 1308), 49.62)
        self.assertEqual(kpi.step_rate(50, 100), 50.0)

    def test_division_by_zero(self):
        self.assertEqual(kpi.ctr(0, 0), 0.0)
        self.assertEqual(kpi.cvr(5, 0), 0.0)
        self.assertIsNone(kpi.cpc(10.0, 0))
        self.assertIsNone(kpi.cpa(10.0, 0))
        self.assertEqual(kpi.activation_rate(3, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
