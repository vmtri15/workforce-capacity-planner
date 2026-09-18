import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workforce_planner.packing import packing_hours, estimated_packing_jobs


class PackingTests(unittest.TestCase):
    def test_job_rounding_per_order(self):
        self.assertEqual(estimated_packing_jobs(25, 24), 2)
        self.assertEqual(estimated_packing_jobs(0, 24), 0)
        self.assertEqual(estimated_packing_jobs(24, 24), 1)
        self.assertNotEqual(sum(estimated_packing_jobs(u, 24) for u in (1, 1)), estimated_packing_jobs(2, 24))

    def test_invalid_job_size(self):
        with self.assertRaises(ValueError):
            estimated_packing_jobs(5, 0)

    def test_zero(self):
        self.assertEqual(packing_hours(0, 0, 60, 4), 0)

    def test_more_items_same_packages(self):
        self.assertAlmostEqual(packing_hours(2, 20, 60, 4)-packing_hours(2, 10, 60, 4), 40/3600)

    def test_more_packages_same_items(self):
        self.assertAlmostEqual(packing_hours(4, 10, 60, 4)-packing_hours(2, 10, 60, 4), 120/3600)

    def test_site_reconciliation(self):
        self.assertAlmostEqual(packing_hours(10, 100, 60, 4), packing_hours(3, 40, 60, 4)+packing_hours(7, 60, 60, 4))

    def test_basic_hours_have_no_hidden_allowance(self):
        self.assertEqual(packing_hours(1, 900, 0, 4), 1)

    def test_invalid(self):
        for args in ((-1, 0, 60, 4), (0, 1, 60, 4), (1, 1, float('nan'), 4)):
            with self.assertRaises(ValueError):
                packing_hours(*args)


if __name__ == "__main__":
    unittest.main()
