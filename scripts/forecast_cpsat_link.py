"""Link a demand forecast to the CP-SAT staffing optimizer and measure what forecast error costs.

The optimizer belongs to the legacy 2011 network model (UCI online retailer data, a 56 day window,
Oct 14 to Dec 8, 2011, three modeled sites, synthetic roster). It is not the 2023 footwear analysis,
so this is a separate experiment on that older model. The 2011 window is the Christmas peak and the
history before it is 22 months, so it is a hard test with one window only.

Forecast: orders, lines and units for the 48 recorded days of the window, made only from days before
Oct 14, 2011. The operating calendar (which dates have orders) is assumed known.

For each forecast model the model's workload feeds the planning engine (which sizes fixed headcount
at the 95th percentile of daily workload) and the optimizer (which plans overtime and temporary
shifts). Three outcomes are compared on the demand that really arrived:
  * hindsight: engine and optimizer on the actual demand (the best a forecast could do)
  * planned on forecast: headcount and overtime/temp shifts planned on the forecast, then replayed
    on the actual demand
  * forecast headcount, day of optimization: headcount sized on the forecast, overtime/temp shifts
    optimized after the actual daily demand is known

Base productivity case only. Wages, rates and the synthetic roster are the model's documented
assumptions, not observed. Uses a temporary copy of data/workforce_planner.db; the original is
not changed.

Run from the project root:
    python3 scripts/forecast_cpsat_link.py
"""
import json
import shutil
import sqlite3
import sys
import tempfile
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import forecast_demand as fd
import forecast_method_check as mc
from workforce_planner.optimization import optimize
from workforce_planner.planning_engine import load_inputs, run_planning_engine
from workforce_planner.roster import build_roster

DB = ROOT / 'data/workforce_planner.db'
PROFILE = ROOT / 'data/processed/uci_daily_workload_profile.csv'
OUT = ROOT / 'data/processed/demand_forecast'
COLUMNS = {'orders': 'distinct_invoice_ids', 'lines': 'positive_quantity_lines', 'units': 'positive_units'}
MODELS = {'SameWeekdayLastYear': mc.seasonal_naive_year, 'Prophet': mc.prophet_yearly,
          'Mean20Days': fd.mean_20_days}


def forecast_window(profile, dates):
    """Forecast each workload column for `dates` using only history before the first date."""
    start = pd.Timestamp(dates[0])
    history = profile[profile['planning_date'] < start].set_index('planning_date')
    calendar = pd.date_range(history.index.min(), start - pd.Timedelta(days=1))
    future = [pd.Timestamp(d).date() for d in dates]
    out = {}
    for model, fn in MODELS.items():
        values = {}
        for key, column in COLUMNS.items():
            hist = history[column].reindex(calendar).astype(float)
            values[key] = np.clip(np.round(fn(hist, future)), 0, None).astype(int)
        out[model] = {d: tuple(int(values[k][i]) for k in COLUMNS) for i, d in enumerate(dates)}
    return out


def build_database(folder, name, window_values=None):
    """Copy the planning database and run the planning engine on it, optionally on other demand."""
    path = Path(folder) / f'{name}.db'
    shutil.copy(DB, path)
    if window_values:
        with sqlite3.connect(path) as connection:
            connection.executemany(
                'UPDATE workload_daily_source SET distinct_invoice_ids=?, positive_quantity_lines=?, '
                'positive_units=? WHERE source_date=?',
                [(o, l, u, d) for d, (o, l, u) in window_values.items()])
    run_planning_engine(path)
    return path


def load_case(path, policy):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        inputs = load_inputs(connection)
        staffing = [dict(r) for r in connection.execute(
            "SELECT * FROM staffing_plans WHERE run_id='base_demand_base_productivity' ORDER BY site_id,role_id")]
        dates = [r[0] for r in connection.execute(
            'SELECT DISTINCT planning_date FROM modeled_daily_workload ORDER BY planning_date')]
        rows = [dict(r) for r in connection.execute('''
            SELECT c.*, s.median_hourly_wage FROM daily_capacity_results c
            JOIN staffing_plans s USING (run_id,site_id,role_id)
            JOIN planning_runs p USING (run_id) WHERE p.productivity_case='base'
            ORDER BY site_id,role_id,planning_date''')]
    roster = build_roster(staffing, dates, inputs.paid_hours, policy['regular_days_per_week'])
    return inputs, staffing, roster, rows


def replay(result, plan_rows, actual_rows, paid, productive, target, temp_factor):
    """Capacity of the planned actions measured against the demand that really arrived."""
    actual = {(r['site_id'], r['role_id'], r['planning_date']): r['workload_quantity'] for r in actual_rows}
    extra_hours = defaultdict(float)
    for group in result['groups']:
        for action in group['actions']:
            factor = temp_factor if action['action'] == 'temporary_shift' else 1.0
            extra_hours[group['site_id'], group['role_id'], action['date']] += action['paid_hours'] * factor
    cells = met = 0
    shortfall = demand_total = 0.0
    for row in plan_rows:
        key = (row['site_id'], row['role_id'], row['planning_date'])
        demand = actual[key]
        if demand == 0:
            continue
        rate = row['productivity_rate']
        capacity = (row['scheduled_headcount'] * paid + extra_hours[key]) * productive * rate
        cells += 1
        met += capacity + 1e-7 >= target * demand
        shortfall += max(0.0, target * demand - capacity)
        demand_total += demand
    return dict(site_role_days=cells, share_meeting_target=met / cells,
                shortfall_workload=shortfall, shortfall_share=shortfall / demand_total)


def summarize(label, plan_rows, result, replayed=None):
    base_cost = sum(r['scheduled_wage_cost'] for r in plan_rows)
    incremental = result['incremental_cost']
    headcount = sum({(r['site_id'], r['role_id']): r['scheduled_headcount'] for r in plan_rows}.values())
    row = dict(case=label, status=result['status'], total_headcount=headcount,
               base_labor_cost=round(base_cost, 2),
               overtime_and_temp_cost=None if incremental is None else round(incremental, 2),
               total_cost=None if incremental is None else round(base_cost + incremental, 2))
    row.update(replayed or {})
    return row


def main():
    warnings.filterwarnings('ignore')
    policy = json.loads((ROOT / 'config/optimization.json').read_text())
    profile = pd.read_csv(PROFILE, parse_dates=['planning_date'])
    rows_out = []
    with tempfile.TemporaryDirectory() as folder:
        actual_db = build_database(folder, 'actual')
        inputs, _, roster, actual_rows = load_case(actual_db, policy)
        paid, productive = inputs.paid_hours, inputs.productive_time_factor
        dates = sorted({r['planning_date'] for r in actual_rows})
        with sqlite3.connect(actual_db) as connection:
            actual_units = dict(connection.execute(
                'SELECT source_date, positive_units FROM workload_daily_source WHERE source_date BETWEEN ? AND ?',
                (inputs.source_window_start, inputs.source_window_end)).fetchall())
        observed = sorted(actual_units)
        hindsight = optimize(actual_rows, roster, policy, paid, productive)
        rows_out.append(summarize('hindsight on actual demand', actual_rows, hindsight))
        print(rows_out[-1], flush=True)

        forecasts = forecast_window(profile, observed)
        for model, values in forecasts.items():
            wape = (sum(abs(values[d][2] - actual_units[d]) for d in observed)
                    / sum(actual_units[d] for d in observed))
            forecast_db = build_database(folder, model, values)
            _, _, forecast_roster, forecast_rows = load_case(forecast_db, policy)
            planned = optimize(forecast_rows, forecast_roster, policy, paid, productive)
            replayed = replay(planned, forecast_rows, actual_rows, paid, productive,
                              policy['service_target'], policy['temp_productivity_factor'])
            rows_out.append(dict(summarize(f'{model}: planned on forecast, replayed on actual',
                                           forecast_rows, planned, replayed), unit_forecast_wape=round(wape, 3)))
            print(rows_out[-1], flush=True)
            # same forecast headcount, but overtime and temp shifts optimized on the actual daily demand
            day_of_rows = [dict(r, workload_quantity=a['workload_quantity'])
                           for r, a in zip(forecast_rows, actual_rows)]
            day_of = optimize(day_of_rows, forecast_roster, policy, paid, productive)
            rows_out.append(dict(summarize(f'{model}: forecast headcount, day of optimization',
                                           forecast_rows, day_of), unit_forecast_wape=round(wape, 3)))
            print(rows_out[-1], flush=True)
    summary = pd.DataFrame(rows_out)
    summary.to_csv(OUT / 'cpsat_link_summary.csv', index=False)
    pd.set_option('display.width', 250)
    pd.set_option('display.max_columns', 20)
    print(summary.to_string(index=False))


if __name__ == '__main__':
    main()
