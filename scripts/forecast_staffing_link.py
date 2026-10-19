"""Link the demand forecast to the staffing decision and measure what forecast error costs.

For each backtest origin in data/processed/demand_forecast/backtest_forecasts.csv (made by
forecast_demand.py), a standing staffing plan is chosen from the forecast, using the same policy grid
as compare_service_costs.py: permanent workers, an overtime limit and a temporary shift limit. The plan
is then replayed on the demand that really arrived, with the planner's own reactive overtime and
temporary shift rules. Plan choice rule: the cheapest policy that reaches the on time target on the
demand it is given.

Compared plans:
  * oracle: chosen with hindsight on the actual demand (the best a forecast could do)
  * forecast: chosen on forecast demand, and on forecast times 1.5 as a safety buffer
  * fixed: the two options in DECISION_ANSWER.md (6 workers and 10 workers, up to 2 overtime hours),
    plus 6 workers with overtime and up to 4 temporary workers kept available as insurance

Wages, overtime and temporary rates are the hypothetical scenario inputs in config/, not observed.
Base case only: 40 units per productive hour, no absences, 1 day temporary lead time.

Run after forecast_demand.py, from the project root:
    python3 scripts/forecast_staffing_link.py
"""
import itertools
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.cost_policy import make_policy
from workforce_planner.service_scenarios import simulate

OUT = ROOT / 'data/processed/demand_forecast'
RATE, ABSENT, LEAD = 40, 0, 1
SOURCES = [('ARIMA', 1.0), ('ARIMA', 1.5), ('Mean20Days', 1.0), ('Mean20Days', 1.5), ('QuantileP90', 1.0)]  # (forecast, buffer)
FIXED = {'fixed_6_workers_ot2': (0, 2, 0), 'fixed_10_workers_ot2': (4, 2, 0),  # extra workers, overtime hours, temps
         'fixed_6_workers_ot2_temps4': (0, 2, 4)}  # not in DECISION_ANSWER.md: 6 workers with overtime and temps kept available

config = json.loads((ROOT / 'config/footwear_scenarios.json').read_text())
costs = json.loads((ROOT / 'config/staffing_cost_scenarios.json').read_text())
GRID = list(itertools.product(costs['extra_permanent_workers'], costs['max_overtime_hours_per_present_worker'],
                              costs['max_temporary_workers_per_day']))


def evaluate(demand, plan):
    extra, overtime, temps = plan
    workers = costs['base_workers'] + extra
    policy = make_policy(workers, ABSENT, RATE, overtime, temps, LEAD, config, costs)
    summary, daily = simulate(demand, workers, ABSENT, RATE, costs['service_operating_days'], config, policy)
    committed = policy.outstanding_shifts() * config['paid_hours'] * costs['temporary_hourly_cost']
    total = sum(r['regular_cost'] + r['overtime_cost'] + r['temporary_cost'] for r in daily) + committed
    share = summary['on_time_unit_share']
    return dict(on_time_share=1.0 if share is None else share, cost=total,
                overtime_hours=sum(r['overtime_paid_hours'] for r in daily))


def choose(demand):
    """Cheapest plan that reaches the on time target on this demand; else the best service."""
    results = [(plan, evaluate(demand, plan)) for plan in GRID]
    ok = [r for r in results if r[1]['on_time_share'] >= config['target_on_time_unit_share']]
    if ok:
        return min(ok, key=lambda r: r[1]['cost'])[0]
    return max(results, key=lambda r: (r[1]['on_time_share'], -r[1]['cost']))[0]


def plan_name(plan):
    return f'extra{plan[0]}_ot{plan[1]}_temps{plan[2]}'


def main():
    bt = pd.read_csv(OUT / 'backtest_forecasts.csv')
    bt['date'] = pd.to_datetime(bt['date']).dt.date
    rows = []
    for origin, g in bt.groupby('origin'):
        known = g.dropna(subset=['actual'])
        if known['date'].nunique() < 10:
            continue
        actual = {d: int(a) for d, a in known.drop_duplicates('date')[['date', 'actual']].values}

        def record(source, plan):
            rows.append(dict(origin=origin, source=source, policy=plan_name(plan), **evaluate(actual, plan)))

        record('oracle', choose(actual))
        for name, plan in FIXED.items():
            record(name, plan)
        for model, buffer in SOURCES:
            m = known[known['model'] == model]
            predicted = {d: max(0, int(round(f * buffer))) for d, f in zip(m['date'], m['forecast'])}
            record(f'{model} x{buffer}', choose(predicted))
    detail = pd.DataFrame(rows)
    oracle = detail[detail['source'] == 'oracle'].set_index('origin')['cost']
    detail['cost_vs_oracle'] = detail['cost'] - detail['origin'].map(oracle)
    detail['met_target'] = detail['on_time_share'] >= config['target_on_time_unit_share']
    summary = detail.groupby('source').agg(
        origins=('origin', 'nunique'), mean_on_time_share=('on_time_share', 'mean'),
        share_missing_target=('met_target', lambda s: 1 - s.mean()), mean_total_cost=('cost', 'mean'),
        mean_cost_vs_oracle=('cost_vs_oracle', 'mean'), mean_overtime_hours=('overtime_hours', 'mean')
    ).reset_index().sort_values('mean_total_cost')
    detail.to_csv(OUT / 'staffing_link_by_origin.csv', index=False)
    summary.to_csv(OUT / 'staffing_link_summary.csv', index=False)
    pd.set_option('display.width', 200)
    print(summary.round(3).to_string(index=False))


if __name__ == '__main__':
    main()
