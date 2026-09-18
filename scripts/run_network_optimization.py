"""Phase 3C: compare expanded workforce actions using the same baseline inputs."""
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import ortools
from workforce_planner.network_optimization import solve_network
from workforce_planner.planning_engine import load_inputs
from workforce_planner.roster import build_roster


def main():
    policy = json.loads((ROOT / 'config/optimization.json').read_text())
    config = json.loads((ROOT / 'config/workforce_actions.json').read_text())
    database = ROOT / 'data/workforce_planner.db'
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        inputs = load_inputs(connection)
        if policy['service_target'] != inputs.service_target:
            raise ValueError('Default policy must match planning target')
        staffing = [dict(row) for row in connection.execute(
            "SELECT * FROM staffing_plans WHERE run_id='base_demand_base_productivity' ORDER BY site_id,role_id")]
        dates = [row[0] for row in connection.execute('SELECT DISTINCT planning_date FROM modeled_daily_workload ORDER BY planning_date')]
        roster = build_roster(staffing, dates, inputs.paid_hours, policy['regular_days_per_week'])
        results = []
        for name, case in [('expanded_base', 'base'), ('expanded_low', 'low'), ('expanded_high', 'high'),
                           ('low_slower_transfers', 'low'),
                           ('low_without_new_actions', 'low'), ('low_delayed_hiring_only', 'low')]:
            scenario_config = copy.deepcopy(config)
            if name == 'low_slower_transfers':
                scenario_config['transfers']['round_trip_paid_travel_hours'] = 4
            if name in ('low_without_new_actions', 'low_delayed_hiring_only'):
                scenario_config['cross_training']['eligible_packers_per_site'] = 0
                scenario_config['transfers']['eligible_pickers_per_site'] = 0
                if name == 'low_without_new_actions':
                    scenario_config['hiring']['candidate_pool_per_site'] = 0
                else:
                    scenario_config['hiring']['recruitment_lead_calendar_days'] = len(dates)
            rows = [dict(row) for row in connection.execute('''
                SELECT c.*, s.median_hourly_wage FROM daily_capacity_results c
                JOIN staffing_plans s USING (run_id,site_id,role_id)
                JOIN planning_runs p USING (run_id)
                WHERE p.productivity_case=? ORDER BY site_id,role_id,planning_date
            ''', (case,))]
            if len(rows) != len(dates) * 6:
                raise ValueError('Incomplete planning inputs')
            result = solve_network(rows, roster, policy, scenario_config, inputs.paid_hours, inputs.productive_time_factor)
            result.update(scenario=name, productivity_case=case)
            results.append(result)
            print(f"{name}: {result['status']}, incremental cost={result['incremental_cost']}", flush=True)
    output = dict(evidence_class='synthetic_workforce_actions_historical_demand_current_policy',
                  solver_version=ortools.__version__, database_sha256=hashlib.sha256(database.read_bytes()).hexdigest(),
                  implementation_sha256=hashlib.sha256((ROOT / 'src/workforce_planner/network_optimization.py').read_bytes()).hexdigest(),
                  paid_hours_per_shift=inputs.paid_hours, productive_time_factor=inputs.productive_time_factor,
                  roster=roster, scenarios=results)
    destination = ROOT / 'data/processed/network_optimization_results.json'
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(output, indent=2) + '\n')
    temporary.replace(destination)
    print(f'Saved {destination}')


if __name__ == '__main__':
    main()
