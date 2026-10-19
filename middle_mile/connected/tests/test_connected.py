import sys
import unittest
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_connected as bc

NET = bc.Network()
T = pd.Timestamp


class ConnectedTest(unittest.TestCase):
    def test_weighted_pick_is_stable_and_follows_the_weights(self):
        weights = {'a': 3, 'b': 1}
        self.assertEqual(bc.weighted_pick('C1', weights, 's'), bc.weighted_pick('C1', weights, 's'))
        counts = Counter(bc.weighted_pick(f'C{i}', weights, 's') for i in range(4000))
        self.assertAlmostEqual(counts['a'] / 4000, 0.75, delta=0.03)

    def test_fifo_completion_follows_capacity(self):
        days = [(date(2023, 1, 2), 5), (date(2023, 1, 3), 5)]
        self.assertEqual(bc.fifo_completion([3, 2, 4, 3], days),
                         [date(2023, 1, 2), date(2023, 1, 2), date(2023, 1, 3), None])

    def test_promise_adds_processing_and_transit_days(self):
        monday = datetime(2023, 1, 2, 9)
        # processing: 2 operating days counting the order day, so Tuesday; Chicago is under 300 km, so 1 more day
        self.assertEqual(NET.promise(monday, 'joliet', 'chicago'), date(2023, 1, 4))
        self.assertEqual(NET.promise(monday, 'joliet', 'minneapolis'), date(2023, 1, 5))

    def test_a_parcel_ready_at_17_reaches_chicago_next_morning(self):
        delivered, trucks = NET.deliver(T('2023-01-02 17:00'), 'joliet', 'chicago')
        self.assertEqual(delivered, date(2023, 1, 3))
        self.assertEqual([t[0] for t in trucks], [('joliet', 'chicago_sc'), ('chicago_sc', 'chicago')])

    def test_a_long_delay_pushes_delivery_a_day(self):
        base, trucks = NET.deliver(T('2023-01-02 17:00'), 'joliet', 'chicago')
        late, _ = NET.deliver(T('2023-01-02 17:00'), 'joliet', 'chicago', lambda t: 8.0 if t == trucks[1] else 0.0)
        self.assertEqual((late - base).days, 1)

    def test_truck_delays_are_the_same_every_run(self):
        truck = (('joliet', 'chicago_sc'), T('2023-01-02 18:00'))
        self.assertEqual(bc.truck_delay()(truck), bc.truck_delay()(truck))


if __name__ == '__main__':
    unittest.main()
