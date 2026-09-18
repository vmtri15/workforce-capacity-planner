import unittest

from scripts.build_2023_network_capacity import allocate_integer, build, nearest_rank


class NetworkCapacity2023Tests(unittest.TestCase):
    def test_nearest_rank(self):
        self.assertEqual(nearest_rank([1, 2, 3, 4, 5], .95), 5)

    def test_integer_allocation_preserves_total(self):
        sites = [
            {'site_id': 'a', 'allocation_share': .43},
            {'site_id': 'b', 'allocation_share': .42},
            {'site_id': 'c', 'allocation_share': .15},
        ]
        allocation = allocate_integer(101, sites)
        self.assertEqual(sum(allocation.values()), 101)
        self.assertEqual(set(allocation), {'a', 'b', 'c'})

    def test_build_preserves_observed_demand_and_case_order(self):
        result = build()
        self.assertEqual(result['metadata']['recorded_dates'], 178)
        self.assertEqual(result['metadata']['observed_units'], 228195)
        self.assertEqual(result['metadata']['source_window_end'], '2023-10-19')
        gaps = [case['network_summary']['gap_hours'] for case in result['cases']]
        self.assertGreaterEqual(gaps[0], gaps[1])
        self.assertGreaterEqual(gaps[1], gaps[2])


if __name__ == '__main__':
    unittest.main()
