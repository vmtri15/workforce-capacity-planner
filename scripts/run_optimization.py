"""Run Phase 3B policy scenarios against a read-only planning database."""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import ortools
from workforce_planner.optimization import optimize, validate_policy
from workforce_planner.planning_engine import load_inputs
from workforce_planner.roster import build_roster


def main():
    policy = json.loads((ROOT / 'config/optimization.json').read_text())
    path = ROOT / 'data/workforce_planner.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        inputs = load_inputs(connection)
        validate_policy(policy, inputs.paid_hours)
        if abs(policy['service_target'] - inputs.service_target) > 1e-8:
            raise ValueError('Default service target must match database assumptions')
        staffing = [dict(row) for row in connection.execute(
            "SELECT * FROM staffing_plans WHERE run_id='base_demand_base_productivity' ORDER BY site_id,role_id")]
        dates = [row[0] for row in connection.execute(
            "SELECT DISTINCT planning_date FROM modeled_daily_workload ORDER BY planning_date")]
        roster = build_roster(staffing, dates, inputs.paid_hours, policy['regular_days_per_week'])
        cases = [('base', 'base', {}), ('low_productivity', 'low', {}), ('high_productivity', 'high', {}),
                 ('overtime_unavailable', 'base', {'ot_unavailable_dates': dates}),
                 ('delayed_temp_no_overtime', 'base', {'ot_unavailable_dates': dates,
                                                       'temp_ready_delay_days': len(dates)}),
                 ('weekly_ot_limit', 'low', {'ot_weekly_hours': 1, 'temp_pool_per_site_role': 0})]
        results = []
        for name, case, overrides in cases:
            rows = [dict(row) for row in connection.execute('''
                SELECT c.*, s.median_hourly_wage FROM daily_capacity_results c
                JOIN staffing_plans s USING (run_id,site_id,role_id)
                JOIN planning_runs p USING (run_id)
                WHERE p.productivity_case=? ORDER BY site_id,role_id,planning_date
            ''', (case,))]
            if len(rows) != len(dates) * 6:
                raise ValueError('Missing daily planning inputs')
            result = optimize(rows, roster, policy | overrides, inputs.paid_hours, inputs.productive_time_factor)
            result.update(scenario=name, productivity_case=case)
            results.append(result)
            print(f"{name}: {result['status']}, incremental cost={result['incremental_cost']}", flush=True)
    output = dict(evidence_class='synthetic_roster_historical_demand_current_policy',
                  solver_version=ortools.__version__, database_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  paid_hours_per_shift=inputs.paid_hours, productive_time_factor=inputs.productive_time_factor,
                  roster=roster, scenarios=results)
    destination = ROOT / 'data/processed/optimization_results.json'
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(output, indent=2) + '\n')
    temporary.replace(destination)
    print(f'Saved {destination}')


if __name__ == '__main__':
    main()
