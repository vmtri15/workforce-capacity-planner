"""Opt-in packing sensitivities with unchanged staffing and action policies."""
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.demand import packing_demand_rows
from workforce_planner.network_optimization import solve_network, required_productive_hours
from workforce_planner.planning_engine import load_inputs
from workforce_planner.roster import build_roster


def main():
    policy = json.loads((ROOT / 'config/optimization.json').read_text())
    actions = json.loads((ROOT / 'config/workforce_actions.json').read_text())
    config = json.loads((ROOT / 'config/packing_scenario.json').read_text())
    if config['allowances_in_task_times']:
        raise ValueError('Packing demand must exclude paid-time allowances')
    source = ROOT / 'data/processed/packing_scenario_daily.csv'
    saved = json.loads((ROOT / 'data/processed/packing_scenario_results.json').read_text())
    if saved['config'] != config:
        raise ValueError('Rebuild packing scenarios after changing configuration')
    with source.open() as f:
        daily = list(csv.DictReader(f))
    database = ROOT / 'data/workforce_planner.db'
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        inputs = load_inputs(conn)
        sites = [dict(r) for r in conn.execute('SELECT * FROM sites ORDER BY site_id')]
        run = 'base_demand_base_productivity'
        baseline_run = dict(conn.execute('SELECT * FROM planning_runs WHERE run_id=?', (run,)).fetchone())
        if baseline_run['demand_scale'] != config['demand_scale'] or baseline_run['service_target'] != policy['service_target']:
            raise ValueError('Packing scale and service policy must match baseline')
        staffing = [dict(r) for r in conn.execute('SELECT * FROM staffing_plans WHERE run_id=?', (run,))]
        rows = [dict(r) for r in conn.execute('''SELECT c.*, s.median_hourly_wage
            FROM daily_capacity_results c JOIN staffing_plans s USING (run_id,site_id,role_id)
            WHERE run_id=? ORDER BY site_id,role_id,planning_date''', (run,))]
    dates = sorted({r['planning_date'] for r in rows})
    if dates[0] != config['source_window_start'] or dates[-1] != config['source_window_end']:
        raise ValueError('Packing and baseline planning windows must match')
    roster = build_roster(staffing, dates, inputs.paid_hours, policy['regular_days_per_week'])
    results = []
    for size in config['units_per_job_sensitivity']:
        demand = packing_demand_rows(rows, daily, sites, size)
        result = solve_network(demand, roster, policy, actions, inputs.paid_hours, inputs.productive_time_factor)
        baseline = []
        for row in demand:
            required = float(required_productive_hours(row))
            available = row['scheduled_headcount'] * inputs.paid_hours * inputs.productive_time_factor
            baseline.append(dict(site_id=row['site_id'], role_id=row['role_id'], planning_date=row['planning_date'],
                required_hours=required, available_productive_hours=available,
                capacity_gap_hours=max(0, required-available),
                service_target_met=int(available+1e-6 >= required*policy['service_target']),
                scheduled_wage_cost=row['scheduled_wage_cost']))
        result.update(scenario=f'packing_{size}_units_per_job', productivity_case='base picking / assumed packing',
                      assumed_units_per_job=size, evidence_class='assumed_uncalibrated',
                      baseline_daily=baseline)
        results.append(result)
        print(f"{result['scenario']}: {result['status']}, cost={result['incremental_cost']}", flush=True)
    paths = ['data/workforce_planner.db', 'data/processed/packing_scenario_daily.csv',
             'config/packing_scenario.json', 'config/optimization.json', 'config/workforce_actions.json',
             'src/workforce_planner/network_optimization.py', 'src/workforce_planner/demand.py',
             'scripts/run_packing_optimization.py', 'src/workforce_planner/roster.py',
             'data/processed/packing_scenario_results.json']
    output = dict(evidence_class='assumed_uncalibrated', demand_basis='productive_hours',
                  config=config, scenarios=results,
                  input_hashes={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})
    destination = ROOT / 'data/processed/packing_optimization_results.json'
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(output, indent=2)+'\n')
    temporary.replace(destination)


if __name__ == '__main__':
    main()
