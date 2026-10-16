import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import evaluate_recovery as er
from build_journeys import load_config

TRUCK = (('SP', 'RJ'), 'dep')


class RecoveryTest(unittest.TestCase):
    def test_overlay_replaces_only_the_named_trucks(self):
        delay = {TRUCK: 4.0, 'other': 1.0}
        overlay = er.Overlay(delay, {TRUCK: 0.0})
        self.assertEqual(overlay.get(TRUCK), 0.0)
        self.assertEqual(overlay.get('other'), 1.0)
        self.assertEqual(overlay.get('missing'), 0.0)

    def test_swap_removes_up_to_the_stated_hours_and_split_removes_all(self):
        swap = {'recovers_hours': 3}
        self.assertEqual(er.option_overrides(TRUCK, {TRUCK: 4.0}, swap)['swap'][TRUCK], 1.0)
        self.assertEqual(er.option_overrides(TRUCK, {TRUCK: 2.0}, swap)['swap'][TRUCK], 0.0)
        self.assertEqual(er.option_overrides(TRUCK, {TRUCK: 4.0}, swap)['split'][TRUCK], 0.0)

    def test_split_cost_has_a_minimum_and_grows_with_distance(self):
        recovery = dict(swap_trailer=dict(cost=300),
                        split_load=dict(extra_truck_cost_per_km=1.0, extra_truck_minimum_cost=500))
        config = load_config()
        short = er.option_costs((('SP', 'RJ'), 'dep'), config, recovery)['split']   # 360 km, below the minimum
        long = er.option_costs((('SP', 'NE'), 'dep'), config, recovery)['split']    # about 1,450 km
        self.assertEqual(short, 500)
        self.assertGreater(long, 1000)

    def test_cheapest_picks_the_lowest_cost_per_parcel_saved_and_skips_useless_options(self):
        options = dict(swap=dict(cost=300, saved=1), split=dict(cost=500, saved=5))
        self.assertEqual(er.cheapest(options), 'split')
        self.assertEqual(er.cheapest(dict(swap=dict(cost=300, saved=0), split=dict(cost=500, saved=0))), None)


if __name__ == '__main__':
    unittest.main()
