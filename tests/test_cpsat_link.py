import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import forecast_cpsat_link as link


class ReplayTest(unittest.TestCase):
    def test_replay_counts_shortfall_against_actual_demand(self):
        # 1 worker, 8 paid hours, productive factor 0.5, rate 10 per hour: baseline capacity 40 per day
        plan = [dict(site_id='s', role_id='r', planning_date=d, scheduled_headcount=1, productivity_rate=10.0)
                for d in ('2011-10-14', '2011-10-15', '2011-10-16')]
        actual = [dict(site_id='s', role_id='r', planning_date=d, workload_quantity=q)
                  for d, q in zip(('2011-10-14', '2011-10-15', '2011-10-16'), (40, 100, 0))]
        result = dict(groups=[dict(site_id='s', role_id='r', actions=[
            dict(date='2011-10-15', action='overtime', paid_hours=2.0),
            dict(date='2011-10-15', action='temporary_shift', paid_hours=8.0)])])
        out = link.replay(result, plan, actual, paid=8, productive=0.5, target=1.0, temp_factor=0.5)
        # day 2 capacity: 40 + (2 + 8 * 0.5) * 0.5 * 10 = 70, short by 30 of 100; day 3 has no demand
        self.assertEqual(out['site_role_days'], 2)
        self.assertEqual(out['share_meeting_target'], 0.5)
        self.assertAlmostEqual(out['shortfall_workload'], 30.0)
        self.assertAlmostEqual(out['shortfall_share'], 30.0 / 140.0)


if __name__ == '__main__':
    unittest.main()
