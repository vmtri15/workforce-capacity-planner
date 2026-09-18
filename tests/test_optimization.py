import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from workforce_planner.optimization import optimize, solve_group, validate_policy


POLICY = json.loads((Path(__file__).resolve().parents[1] / 'config/optimization.json').read_text())


class OptimizationTests(unittest.TestCase):
    def solve(self, quantities, *, start='2026-09-14', headcount=1, **overrides):
        policy = POLICY | dict(service_target=1, temp_productivity_factor=1,
                               temp_ready_delay_days=0, temp_pool_per_site_role=2) | overrides
        rows = [dict(planning_date=(date.fromisoformat(start) + timedelta(days=i)).isoformat(),
                     site_id='a', role_id='picker', productivity_rate=1,
                     median_hourly_wage=1, scheduled_headcount=headcount, workload_quantity=quantity)
                for i, quantity in enumerate(quantities)]
        roster = {'workers': [dict(worker_id='w', site_id='a', role_id='picker',
                                   weekdays=[0, 1, 2, 3, 4])] if headcount else []}
        return optimize(rows, roster, policy, 8, 1)

    def test_known_mixed_optimum(self):
        # 10 extra units: 2 overtime hours + 8h temporary shift costs 3+12.
        result = self.solve([18])
        self.assertEqual(result['status'], 'OPTIMAL')
        self.assertEqual(result['incremental_cost'], 15)
        self.assertEqual({a['action'] for a in result['groups'][0]['actions']},
                         {'overtime', 'temporary_shift'})

    def test_weekly_cap_changes_feasibility(self):
        self.assertEqual(self.solve([10, 10], temp_pool_per_site_role=0)['status'], 'OPTIMAL')
        result = self.solve([10, 10], temp_pool_per_site_role=0, ot_weekly_hours=2)
        self.assertEqual(result['status'], 'INFEASIBLE')
        self.assertIsNone(result['incremental_cost'])

    def test_readiness_and_availability_block_assignment(self):
        for overrides in ({'temp_ready_delay_days': 1},
                          {'temp_unavailable_dates': ['2026-09-14']}):
            result = self.solve([10], ot_daily_hours=0, **overrides)
            self.assertEqual(result['status'], 'INFEASIBLE')
            self.assertTrue(result['groups'][0]['daily_capacity_upper_bound_shortfalls'])

    def test_partial_week_reserves_regular_hours_outside_window(self):
        result = self.solve([10], start='2026-09-18', temp_pool_per_site_role=0, weekly_total_hours=40)
        self.assertEqual(result['status'], 'INFEASIBLE')

    def test_rolling_rest_spans_calendar_week(self):
        # Fri-Thu: calendar weeks alone allow 3+4 shifts, rolling seven must reject.
        result = self.solve([8] * 7, headcount=0, start='2026-09-18', temp_pool_per_site_role=1)
        self.assertEqual(result['status'], 'INFEASIBLE')

    def test_zero_gap_needs_no_added_labor(self):
        result = self.solve([0])
        self.assertEqual(result['status'], 'OPTIMAL')
        self.assertEqual(result['incremental_cost'], 0)
        self.assertEqual(result['groups'][0]['actions'], [])

    def test_invalid_policy(self):
        for change in ({'ot_weekly_hours': -1}, {'temp_pool_per_site_role': 1.5},
                       {'ot_step_hours': 0}, {'service_target': float('nan')},
                       {'temp_wage_multiplier': float('inf')},
                       {'ot_unavailable_dates': ['20260914']},
                       {'temp_unavailable_dates': '2026-09-14'}):
            with self.assertRaises(ValueError):
                validate_policy(POLICY | change, 8)

    def test_empty_or_changing_inputs_rejected(self):
        with self.assertRaises(ValueError):
            optimize([], {'workers': []}, POLICY, 8, 1)
        rows = [dict(planning_date='2026-09-14', site_id='a', role_id='picker',
                     productivity_rate=1, median_hourly_wage=1, scheduled_headcount=0, workload_quantity=0),
                dict(planning_date='2026-09-15', site_id='a', role_id='picker',
                     productivity_rate=0.5, median_hourly_wage=1, scheduled_headcount=0, workload_quantity=0)]
        with self.assertRaisesRegex(ValueError, 'constant productivity_rate'):
            solve_group(rows, [], POLICY, 8, 1)


if __name__ == '__main__':
    unittest.main()
