import unittest

from scripts.profile_soto_pinedo import build, numeric_summary, percentile


class SotoPinedoProfileTests(unittest.TestCase):
    def test_percentile_and_summary(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], .5), 3)
        self.assertEqual(numeric_summary([1, 2, None, "3"])["observations"], 2)

    def test_build_is_aggregate_and_privacy_safe(self):
        result = build()
        self.assertEqual(result["picking_benchmarks"]["operator_columns"], 8)
        self.assertGreater(result["preparation_2025"]["rows"], 0)
        self.assertGreater(result["fulfillment_coverage"]["records"], 0)
        serialized = str(result).lower()
        self.assertNotIn("cliente", serialized)
        self.assertNotIn("placa", serialized)


if __name__ == "__main__":
    unittest.main()
