import copy
from decimal import Decimal
import unittest

import test_network_optimization as fixtures
from workforce_planner.demand import packing_demand_rows
from workforce_planner.network_optimization import PACK, PICK, solve_network


class DemandTests(unittest.TestCase):
    def test_allocation_preserves_hours_and_picking(self):
        rows = [dict(site_id=s, role_id=r, planning_date='2026-09-14', workload_quantity=12,
                     productivity_rate=3) for s in ['a', 'b'] for r in [PICK, PACK]]
        original = copy.deepcopy(rows)
        daily = [dict(source_date='2026-09-14', assumed_units_per_job=24, productive_packing_hours='11.123456')]
        sites = [dict(site_id='a', allocation_share=.43), dict(site_id='b', allocation_share=.57)]
        result = packing_demand_rows(rows, daily, sites, 24)
        self.assertEqual(sum(Decimal(r['productive_demand_hours']) for r in result if r['role_id']==PACK),Decimal('11.123456'))
        self.assertEqual(rows, original)
        self.assertNotIn('productive_demand_hours',result[0])
        with self.assertRaisesRegex(ValueError, 'matching record'):
            packing_demand_rows(rows, daily*2, sites, 24)

    def solve_hours(self, hours, **overrides):
        fixture=fixtures.NetworkTests()
        rows, roster=fixture.case_inputs({('a',PACK):[999999]}, {('a',PACK)})
        rows[0]['productive_demand_hours']=hours
        policy=fixtures.POLICY | dict(service_target=1, ot_daily_hours=0, temp_pool_per_site_role=0) | overrides
        return solve_network(rows,roster,policy,fixture.config(),8,.85)

    def test_hours_override_quantity_and_availability_applied_once(self):
        result=self.solve_hours('6.8')
        self.assertEqual(result['status'],'OPTIMAL')
        self.assertEqual(result['incremental_cost'],0)
        self.assertEqual(result['daily_results'][0]['available_productive_hours'],6.8)
        self.assertNotIn('capacity_quantity',result['daily_results'][0])
        result=self.solve_hours('6.81')
        self.assertEqual(result['status'],'INFEASIBLE')
        self.assertIsNone(result['incremental_cost'])
        self.assertEqual(result['actions'],[])

    def test_overtime_uses_productive_hours(self):
        result=self.solve_hours('7.65',ot_daily_hours=2)
        self.assertEqual(result['status'],'OPTIMAL')
        self.assertAlmostEqual(sum(a['paid_hours'] for a in result['actions']),1)

    def test_temporary_worker_productivity_applied_once(self):
        result=self.solve_hours('12.24',temp_pool_per_site_role=1,temp_ready_delay_days=0)
        self.assertEqual(result['status'],'OPTIMAL')
        self.assertEqual(result['actions'][0]['kind'],'temporary_shift')
        self.assertAlmostEqual(result['daily_results'][0]['available_productive_hours'],12.24)

    def test_invalid_hours_rejected(self):
        for value in ['-1','NaN','Infinity']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.solve_hours(value)

    def test_training_cannot_take_needed_packing_hours(self):
        fixture=fixtures.NetworkTests()
        config=fixture.config()
        config['cross_training'].update(eligible_packers_per_site=1,picking_productivity_factor=1)
        rows,roster=fixture.case_inputs({('a',PACK):[0,0],('a',PICK):[6.8,8.5]}, {('a',PACK),('a',PICK)})
        for row in rows:
            if row['role_id']==PACK:
                row['productive_demand_hours']='6.8'
        policy=fixtures.POLICY | dict(service_target=1,ot_daily_hours=0,temp_pool_per_site_role=0)
        result=solve_network(rows,roster,policy,config,8,.85)
        self.assertEqual(result['status'],'INFEASIBLE')


if __name__=='__main__':
    unittest.main()
