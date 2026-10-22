import random
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'last_mile'))
import build_last_mile as lm


class LastMileTest(unittest.TestCase):
    def test_oversized_stop_is_split_into_van_loads(self):
        cap = lm.CONFIG['van_capacity_units']
        loads = [u for _, u in lm.split_stops([((0, 0), 2 * cap + 7)])]
        self.assertEqual(loads, [cap, cap, 7])

    def test_routes_serve_every_stop_within_van_capacity(self):
        rng = random.Random(3)
        depot = (41.88, -87.63)
        stops = [((41.88 + rng.uniform(-.3, .3), -87.63 + rng.uniform(-.3, .3)), rng.randint(1, 120)) for _ in range(30)]
        vans, km, routes = lm.route_day(depot, stops)
        loads = lm.split_stops(stops)
        served = sorted(i for route in routes for i in route)
        self.assertEqual(served, list(range(len(loads))))
        for route in routes:
            self.assertLessEqual(sum(loads[i][1] for i in route), lm.CONFIG['van_capacity_units'])
        self.assertEqual(vans, len(routes))
        self.assertGreater(km, 0)

    def test_customer_point_is_fixed_and_inside_the_delivery_radius(self):
        station = lm.mm.CONFIG['stations']['chicago']
        a, b = lm.customer_point('C1', 'chicago'), lm.customer_point('C1', 'chicago')
        self.assertEqual(a, b)
        distance = lm.mm.haversine_km(station['lat'], station['lng'], a[0], a[1])
        self.assertLessEqual(distance, lm.CONFIG['delivery_radius_km']['chicago'] + 0.5)

    def test_fuel_cost_uses_that_weeks_diesel_price(self):
        prices = lm.pd.Series([4.0, 5.0], index=lm.pd.to_datetime(['2023-01-02', '2023-01-09']))
        with mock.patch.object(lm, '_diesel', prices):
            per_km = lambda price: lm.CONFIG['fuel_gallons_per_km'] * price + lm.CONFIG['other_cost_per_km']
            self.assertAlmostEqual(lm.km_cost('2023-01-05'), per_km(4.0))  # the week starting Jan 2
            self.assertAlmostEqual(lm.km_cost('2023-01-10'), per_km(5.0))
            self.assertAlmostEqual(lm.km_cost(), per_km(4.5))  # 2023 average

    def test_fleet_choice_is_never_worse_than_owning_for_peak_or_contracting_everything(self):
        fleet = lm.best_fleet([0, 1, 2, 2, 5, 1, 0], km_cost=100.0)
        self.assertLessEqual(fleet['cost'], fleet['cost_owning_for_peak'])
        self.assertLessEqual(fleet['cost'], fleet['cost_all_contracted'])


if __name__ == '__main__':
    unittest.main()
