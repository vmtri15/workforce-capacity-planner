import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import simulate_disruptions as sd
from build_journeys import load_config

CONFIG = load_config()
NET = sd.Network(CONFIG)
T = pd.Timestamp
LANE = ('SP', 'RJ')  # 360 km: 1 hour loading + 6.0 hours driving, so a 06:00 truck arrives about 13:00


class EngineTest(unittest.TestCase):
    def test_no_disruption_gives_the_scheduled_arrival(self):
        arrival, used = sd.run_parcel(T('2018-01-01 01:00'), [LANE], NET)  # ready 04:00, takes the 06:00 truck
        self.assertEqual(used[0][1], T('2018-01-01 06:00'))
        self.assertLess(abs(arrival - T('2018-01-01 13:00')), pd.Timedelta(minutes=2))  # 360 km at 60 km/h plus loading

    def test_a_delay_past_the_cutoff_slips_the_parcel_one_day(self):
        base, used = sd.run_parcel(T('2018-01-01 01:00'), [LANE], NET)
        late, _ = sd.run_parcel(T('2018-01-01 01:00'), [LANE], NET, delay={used[0]: 8.0})  # arrives about 21:01
        self.assertEqual(sd.slip_days(late, base, 20), 1)
        small, _ = sd.run_parcel(T('2018-01-01 01:00'), [LANE], NET, delay={used[0]: 2.0})
        self.assertEqual(sd.slip_days(small, base, 20), 0)

    def test_a_cancelled_lane_day_sends_the_parcel_on_the_next_day(self):
        _, used = sd.run_parcel(T('2018-01-01 01:00'), [LANE], NET, cancelled={(LANE, T('2018-01-01').date())})
        self.assertEqual(used[0][1], T('2018-01-02 06:00'))

    def test_a_closed_hub_holds_parcels_until_it_reopens(self):
        closed = {'SP': {T('2018-01-01').date()}}
        _, used = sd.run_parcel(T('2018-01-01 01:00'), [LANE], NET, closed=closed)
        self.assertEqual(used[0][1], T('2018-01-02 06:00'))

    def test_a_late_first_leg_misses_the_connection_at_the_main_hub(self):
        lanes = [('RJ', 'SP'), ('SP', 'MG')]
        base, used = sd.run_parcel(T('2018-01-01 01:00'), lanes, NET)
        _, used_late = sd.run_parcel(T('2018-01-01 01:00'), lanes, NET, delay={used[0]: 30.0})
        self.assertGreater(used_late[1][1], used[1][1])

    def test_breach_kinds(self):
        self.assertEqual(sd.breach_kind(0.5, 1), 'new')
        self.assertIsNone(sd.breach_kind(2.0, 1))
        self.assertEqual(sd.breach_kind(-1.0, 1), 'worse')
        self.assertIsNone(sd.breach_kind(0.5, 0))


if __name__ == '__main__':
    unittest.main()
