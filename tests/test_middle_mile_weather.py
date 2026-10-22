import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'middle_mile' / 'connected'))
import build_connected as mm


class WeatherDelayTest(unittest.TestCase):
    def test_snow_at_either_end_adds_the_lost_driving_time(self):
        net = mm.Network()
        truck = (('joliet', 'milwaukee_sc'), pd.Timestamp('2023-01-25 18:00'))
        calm = mm.truck_delay(net.c, net, weather=False)(truck)
        snow_day = {('milwaukee_sc', truck[1].date()): 0.25}
        with mock.patch.object(mm, 'weather_slowdown', return_value=snow_day):
            snowy = mm.truck_delay(net.c, net)(truck)
        drive = net.drive_hours('joliet', 'milwaukee_sc')
        self.assertAlmostEqual(snowy - calm, drive * (1 / 0.75 - 1))

    def test_a_calm_day_adds_nothing(self):
        net = mm.Network()
        truck = (('ohare', 'chicago_sc'), pd.Timestamp('2023-07-10 22:00'))
        with mock.patch.object(mm, 'weather_slowdown', return_value={}):
            self.assertEqual(mm.truck_delay(net.c, net)(truck), mm.truck_delay(net.c, net, weather=False)(truck))


class TruckRoadTest(unittest.TestCase):
    def test_lane_time_uses_the_real_truck_route_when_present(self):
        net = mm.Network()
        net.roads = {('chicago_sc', 'indianapolis'): 4.7}
        self.assertEqual(net.lane_time(('chicago_sc', 'indianapolis')), (net.c['loading_hours'] + 4.7) * mm.HOUR)
        straight = net.km('ohare', 'chicago_sc') / net.c['truck_speed_kmh']
        self.assertAlmostEqual(net.drive_hours('ohare', 'chicago_sc'), straight)  # no route fetched: straight line


if __name__ == '__main__':
    unittest.main()
