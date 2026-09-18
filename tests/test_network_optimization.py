import copy
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from workforce_planner.network_optimization import PACK, PICK, audit_solution, solve_network

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / 'config/optimization.json').read_text())
CONFIG = json.loads((ROOT / 'config/workforce_actions.json').read_text())


class NetworkTests(unittest.TestCase):
    def config(self):
        config = copy.deepcopy(CONFIG)
        config['cross_training']['eligible_packers_per_site'] = 0
        config['hiring']['candidate_pool_per_site'] = 0
        config['transfers']['eligible_pickers_per_site'] = 0
        config['transfers']['allowed_routes'] = []
        config['solver_seconds'] = 2
        return config

    def case_inputs(self, demands, workers):
        dates = [(date(2026, 9, 14) + timedelta(days=i)).isoformat() for i in range(len(next(iter(demands.values()))))]
        roster = {'workers': [dict(worker_id=f'w:{site}:{role}', site_id=site, role_id=role,
                                   weekdays=[0, 1, 2, 3, 4]) for site, role in workers]}
        rows = [dict(site_id=site, role_id=role, planning_date=day, workload_quantity=values[i],
                     scheduled_headcount=int((site, role) in workers), productivity_rate=1, median_hourly_wage=1)
                for (site, role), values in demands.items() for i, day in enumerate(dates)]
        return rows, roster

    def run_case(self, demands, workers, config):
        rows, roster = self.case_inputs(demands, workers)
        policy = POLICY | dict(service_target=1, ot_daily_hours=0, temp_pool_per_site_role=0)
        return solve_network(rows, roster, policy, config, 8, 1)

    def hire_audit_fixture(self):
        config = self.config()
        config['hiring'].update(candidate_pool_per_site=1, recruitment_lead_calendar_days=0,
                                paid_training_days=2, productive_factor_after_training=1,
                                recruitment_and_external_training_fee=10)
        demands = {('a', PICK): [0, 0, 8, 0, 0]}
        result = self.run_case(demands, set(), config)
        rows, roster = self.case_inputs(demands, set())
        return result, rows, roster

    def test_audit_rejects_unpaid_quiet_hiring_day(self):
        result, rows, roster = self.hire_audit_fixture()
        action = result['actions'][0]
        action['production_dates'].pop()
        action['paid_hours'] -= 8
        action['incremental_cost'] -= 8
        result['incremental_cost'] -= 8
        with self.assertRaisesRegex(ValueError, 'guaranteed paid schedule'):
            audit_solution(result, rows, roster, 8, 1)

    def test_audit_rejects_missing_hire_eligibility(self):
        result, rows, roster = self.hire_audit_fixture()
        result['eligibility']['hiring'] = []
        with self.assertRaisesRegex(ValueError, 'Hire eligibility'):
            audit_solution(result, rows, roster, 8, 1)

    def test_audit_rejects_duplicate_hire(self):
        result, rows, roster = self.hire_audit_fixture()
        result['actions'].append(copy.deepcopy(result['actions'][0]))
        result['incremental_cost'] *= 2
        with self.assertRaisesRegex(ValueError, 'Duplicate worker action'):
            audit_solution(result, rows, roster, 8, 1)

    def test_hiring_schedule_must_respect_configured_weekly_policy(self):
        config = self.config()
        config['hiring']['candidate_pool_per_site'] = 1
        rows, roster = self.case_inputs({('a', PICK): [0]}, set())
        policy = POLICY | dict(regular_days_per_week=4)
        with self.assertRaisesRegex(ValueError, 'Hiring schedule exceeds'):
            solve_network(rows, roster, policy, config, 8, 1)

    def test_training_consumes_capacity_and_enables_later_work(self):
        config = self.config()
        config['cross_training'].update(eligible_packers_per_site=1, picking_productivity_factor=1)
        result = self.run_case({('a', PACK): [4, 6], ('a', PICK): [8, 10]}, {('a', PACK), ('a', PICK)}, config)
        self.assertEqual(result['status'], 'OPTIMAL')
        self.assertEqual(result['incremental_cost'], 100)
        self.assertEqual({a['kind'] for a in result['actions']}, {'cross_training', 'cross_role_work'})

    def test_training_cannot_supply_same_day_capacity(self):
        config = self.config()
        config['cross_training'].update(eligible_packers_per_site=1, picking_productivity_factor=1)
        result = self.run_case({('a', PACK): [4, 6], ('a', PICK): [10, 8]}, {('a', PACK), ('a', PICK)}, config)
        self.assertEqual(result['status'], 'INFEASIBLE')

    def test_cross_training_preserves_packing_target(self):
        config = self.config()
        config['cross_training'].update(eligible_packers_per_site=1, picking_productivity_factor=1)
        result = self.run_case({('a', PACK): [4, 8], ('a', PICK): [8, 10]}, {('a', PACK), ('a', PICK)}, config)
        self.assertEqual(result['status'], 'INFEASIBLE')

    def test_hire_pays_training_and_all_scheduled_days(self):
        config = self.config()
        config['hiring'].update(candidate_pool_per_site=1, recruitment_lead_calendar_days=0,
                                paid_training_days=2, productive_factor_after_training=1,
                                recruitment_and_external_training_fee=10)
        result = self.run_case({('a', PICK): [0, 0, 8, 0, 0]}, set(), config)
        self.assertEqual(result['status'], 'OPTIMAL')
        self.assertEqual(result['incremental_cost'], 50)  # 5 paid days, including 2 in training, plus fee.
        self.assertEqual(result['actions'][0]['paid_training_hours'], 16)
        self.assertEqual(result['actions'][0]['ready_date'], '2026-09-16')

    def test_hiring_delay_can_make_target_unreachable(self):
        config = self.config()
        config['hiring'].update(candidate_pool_per_site=1, recruitment_lead_calendar_days=1, paid_training_days=2)
        result = self.run_case({('a', PICK): [0, 0, 8]}, set(), config)
        self.assertEqual(result['status'], 'INFEASIBLE')
        self.assertIsNone(result['incremental_cost'])

    def test_transfer_loses_paid_travel_time(self):
        config = self.config()
        config['transfers'].update(eligible_pickers_per_site=1, destination_readiness_delay_days=0,
                                   allowed_routes=[['a', 'b']])
        result = self.run_case({('a', PICK): [0], ('b', PICK): [14]}, {('a', PICK), ('b', PICK)}, config)
        self.assertEqual(result['status'], 'OPTIMAL')
        self.assertEqual(result['incremental_cost'], 25)
        config['transfers']['round_trip_paid_travel_hours'] = 3
        self.assertEqual(self.run_case({('a', PICK): [0], ('b', PICK): [14]},
                                      {('a', PICK), ('b', PICK)}, config)['status'], 'INFEASIBLE')

    def test_transfer_cannot_create_donor_shortage(self):
        config = self.config()
        config['transfers'].update(eligible_pickers_per_site=1, destination_readiness_delay_days=0,
                                   allowed_routes=[['a', 'b']])
        result = self.run_case({('a', PICK): [1], ('b', PICK): [14]}, {('a', PICK), ('b', PICK)}, config)
        self.assertEqual(result['status'], 'INFEASIBLE')

    def test_worker_cannot_transfer_to_two_sites_at_once(self):
        config = self.config()
        config['transfers'].update(eligible_pickers_per_site=1, destination_readiness_delay_days=0,
                                   allowed_routes=[['a', 'b'], ['a', 'c']])
        result = self.run_case({('a', PICK): [0], ('b', PICK): [14], ('c', PICK): [14]},
                               {('a', PICK), ('b', PICK), ('c', PICK)}, config)
        self.assertEqual(result['status'], 'INFEASIBLE')

    def test_zero_shortage_selects_no_actions(self):
        result = self.run_case({('a', PICK): [0]}, {('a', PICK)}, self.config())
        self.assertEqual(result['incremental_cost'], 0)
        self.assertEqual(result['actions'], [])


if __name__ == '__main__':
    unittest.main()
