from datetime import date
import unittest

from workforce_planner.service_scenarios import deadline, simulate

CONFIG = dict(paid_hours=1, productive_factor=1, operating_weekdays=[0,1,2,3,4],
              recovery_calendar_days=5, initial_backlog_units=0, overtime_hours=0,
              temporary_workers=0, target_on_time_unit_share=.95)


class ServiceScenarioTests(unittest.TestCase):
    def test_weekend_deadline(self):
        self.assertEqual(deadline(date(2023,1,6),2,CONFIG['operating_weekdays']),date(2023,1,9))
        self.assertEqual(deadline(date(2023,1,7),1,CONFIG['operating_weekdays']),date(2023,1,9))

    def test_late_completion_not_counted_on_time(self):
        r, days = simulate({date(2023,1,6):15},1,0,10,1,CONFIG)
        self.assertEqual((r['completed_on_time'],r['completed_late']),(10,5))
        self.assertFalse(r['target_met'])
        self.assertEqual(days[0]['past_due_at_close'],5)
        r,_ = simulate({date(2023,1,6):15},1,0,10,2,CONFIG)
        self.assertTrue(r['target_met'])

    def test_unfinished_and_censoring(self):
        cfg = CONFIG | dict(recovery_calendar_days=0)
        r,_ = simulate({date(2023,1,6):15},1,1,10,1,cfg)
        self.assertEqual(r['overdue_unfinished'],15)
        self.assertFalse(r['target_met'])
        r,_ = simulate({date(2023,1,6):15},1,1,10,2,cfg)
        self.assertEqual(r['pending_not_due'],15)
        self.assertIsNone(r['target_met'])

    def test_conservation_absence_and_monotonicity(self):
        demand={date(2023,1,5):50,date(2023,1,6):20}
        normal,rows=simulate(demand,3,0,10,1,CONFIG)
        absent,_=simulate(demand,3,1,10,1,CONFIG)
        self.assertGreaterEqual(normal['on_time_unit_share'],absent['on_time_unit_share'])
        self.assertEqual(normal['arrivals'],sum(normal[k] for k in
                         ['completed_on_time','completed_late','overdue_unfinished','pending_not_due']))
        for r in rows:
            self.assertEqual(r['opening_backlog']+r['arrivals'],
                             r['completed_on_time']+r['completed_late']+r['closing_backlog'])

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            deadline(date(2023,1,5),1,[])
        with self.assertRaises(ValueError):
            simulate({date(2023,1,5):5},1,2,10,1,CONFIG)
        with self.assertRaises(ValueError):
            simulate({date(2023,1,5):5},1,0,float('nan'),1,CONFIG)


if __name__ == '__main__':
    unittest.main()
