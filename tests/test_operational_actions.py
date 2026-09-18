import importlib.util
from datetime import date
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('actions', Path(__file__).resolve().parents[1] / 'scripts/analyze_operational_actions.py')
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)


class OperationalActionsTests(unittest.TestCase):
    def test_segments_and_identity(self):
        row = dict(orderNumber='1', creationDate='05/01/2023 07:00', codCustomer='A',
                   **{'quantity (units)': '3'})
        self.assertEqual(actions.segment_orders([row,row])[0]['segment'], 'large_over_5')
        with self.assertRaises(ValueError):
            actions.segment_orders([row,dict(row,codCustomer='B')])

    def test_size_normalization(self):
        self.assertEqual(actions.size_key('9'),actions.size_key('9.0'))
        self.assertEqual(actions.size_key(''), 'MISSING')

    def test_packing_scope(self):
        self.assertEqual(actions.packing_seconds(2,60,10),80)
        for n in [0,6,2.5,True]:
            with self.assertRaises(ValueError):
                actions.packing_seconds(n,60,10)

    def test_policy_capacity_and_delay(self):
        demand = {date(2023,1,5): 5000, date(2023,1,6): 0}
        base,_ = actions.response_case(demand,40,'carryover')
        ot,_ = actions.response_case(demand,40,'overtime')
        temp,rows = actions.response_case(demand,40,'temporary')
        self.assertEqual(rows[0]['extra_paid_hours'],0)
        self.assertEqual(rows[1]['extra_paid_hours'],16)
        self.assertLess(ot['backlog_unit_days'],base['backlog_unit_days'])
        self.assertLess(temp['backlog_unit_days'],base['backlog_unit_days'])
        self.assertTrue(all(r['opening_backlog']+r['arrivals']==r['completed']+r['closing_backlog'] for r in rows))

    def test_capacity_rounding(self):
        _, rows = actions.response_case({date(2023,1,5): 5000},50,'carryover')
        self.assertEqual(rows[0]['capacity'],2040)


if __name__ == '__main__':
    unittest.main()
