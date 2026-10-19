import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_journeys as bj

CONFIG = bj.load_config()
T = pd.Timestamp


class JourneyTest(unittest.TestCase):
    def test_next_departure_picks_the_first_truck_at_or_after_ready(self):
        deps = CONFIG['departures']
        self.assertEqual(bj.next_departure(T('2018-01-01 05:00'), deps), T('2018-01-01 06:00'))
        self.assertEqual(bj.next_departure(T('2018-01-01 06:00'), deps), T('2018-01-01 06:00'))
        self.assertEqual(bj.next_departure(T('2018-01-01 06:01'), deps), T('2018-01-01 18:00'))
        self.assertEqual(bj.next_departure(T('2018-01-01 18:01'), deps), T('2018-01-02 06:00'))

    def test_wave_date_depends_on_the_cutoff(self):
        self.assertEqual(bj.wave_date(T('2018-01-01 19:59'), 20).isoformat(), '2018-01-02')
        self.assertEqual(bj.wave_date(T('2018-01-01 20:00'), 20).isoformat(), '2018-01-02')
        self.assertEqual(bj.wave_date(T('2018-01-01 20:01'), 20).isoformat(), '2018-01-03')

    def test_every_state_is_assigned_to_exactly_one_hub(self):
        mapping = bj.state_to_hub(CONFIG)
        self.assertEqual(len(mapping), 27)

    def test_full_truck_pushes_the_next_parcel_to_the_next_departure(self):
        ready = pd.Series([T('2018-01-01 05:00')] * 3)
        lanes = [('SP', 'RJ')] * 3
        dep, _ = bj.schedule_leg(ready, lanes, CONFIG, capacity={('SP', 'RJ'): 2})
        self.assertEqual(list(dep), [T('2018-01-01 06:00')] * 2 + [T('2018-01-01 18:00')])

    def test_parcels_between_spokes_go_through_the_main_hub(self):
        row = dict(order_id='a', seller_state='RJ', customer_state='MG', handover_ts=T('2018-01-01 08:00'),
                   promised_ts=T('2018-01-20'), delivered_ts=T('2018-01-10'), weight_g=500)
        local = dict(row, order_id='b', seller_state='SP', customer_state='SP')
        journeys, legs, trucks, caps = bj.build(pd.DataFrame([row, local]), CONFIG)
        self.assertEqual(list(journeys['order_id']), ['a'])  # the same hub parcel has no truck leg
        self.assertEqual(int(journeys.iloc[0]['n_legs']), 2)
        self.assertEqual(list(legs.sort_values('leg')[['from_hub', 'to_hub']].itertuples(index=False, name=None)),
                         [('RJ', 'SP'), ('SP', 'MG')])


if __name__ == '__main__':
    unittest.main()
