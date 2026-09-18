from datetime import date
import unittest
from workforce_planner.cost_policy import make_policy
from workforce_planner.service_scenarios import simulate

CONFIG=dict(paid_hours=8,productive_factor=.85,operating_weekdays=[0,1,2,3,4],
            recovery_calendar_days=7,initial_backlog_units=0,overtime_hours=0,
            temporary_workers=0,target_on_time_unit_share=.95)
COSTS=dict(regular_hourly_cost=22,overtime_multiplier=1.5,temporary_hourly_cost=30,
           temporary_productivity_factor=.8)


class CostPolicyTests(unittest.TestCase):
    def test_no_action_matches_original(self):
        demand={date(2023,1,5):5000}
        original,_=simulate(demand,6,0,40,2,CONFIG)
        result,rows=simulate(demand,6,0,40,2,CONFIG,make_policy(6,0,40,0,0,1,CONFIG,COSTS))
        self.assertEqual(original,result)
        self.assertEqual(rows[0]['regular_cost'],1056)

    def test_overtime_due_trigger_cap_and_cost(self):
        day=date(2023,1,5)
        policy=make_policy(6,1,40,2,0,1,CONFIG,COSTS)
        capacity,fields=policy(day,((day,5000),),1360)
        self.assertEqual(fields['overtime_paid_hours'],10)
        self.assertEqual(fields['overtime_cost'],330)
        self.assertEqual(capacity,1700)
        self.assertEqual(fields['regular_cost'],1056)

    def test_booking_delay_and_uncancellable_cost(self):
        policy=make_policy(6,0,40,0,2,1,CONFIG,COSTS)
        fri=date(2023,1,6)
        _,f=policy(fri,((fri,10000),),1632)
        self.assertEqual(f['temporary_workers'],0)
        self.assertEqual(f['booked_future_workers'],2)
        _,weekend=policy(date(2023,1,7),(),0)
        self.assertEqual(weekend['regular_cost'],0)
        cap,mon=policy(date(2023,1,9),(),1632)
        self.assertEqual(mon['temporary_workers'],2)
        self.assertEqual(mon['temporary_cost'],480)
        self.assertEqual(cap,2067)

    def test_invalid_lead(self):
        with self.assertRaises(ValueError):
            make_policy(6,0,40,0,2,0,CONFIG,COSTS)


if __name__=='__main__':
    unittest.main()
