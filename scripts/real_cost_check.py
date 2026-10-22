"""Does the staffing recommendation hold at real 2023 labor costs?

Replays the three fixed staffing plans on the same 25 four week windows of actual 2023 demand as
forecast_staffing_link.py, once at the model's assumed hourly costs and once at real costs from BLS
(scripts/fetch_bls_benchmarks.py): permanent workers at average warehouse pay times the employer cost multiplier,
temps at temp agency pay times an assumed agency markup. Service is the same in both runs; only cost changes.
Writes data/processed/real_cost_check.csv. Run from the repo root, after forecast_demand.py:
    .venv/bin/python scripts/real_cost_check.py
"""
import json
from pathlib import Path

import pandas as pd

import forecast_staffing_link as link

ROOT = Path(__file__).resolve().parents[1]
BLS = ROOT / 'data/processed/bls_2023_benchmarks.json'
OUT = ROOT / 'data/processed/real_cost_check.csv'


def replay(rates):
    """Mean cost and service of each fixed plan over the backtest windows, at the given hourly rates."""
    link.costs.update(rates)  # evaluate() reads the module's cost table
    bt = pd.read_csv(link.OUT / 'backtest_forecasts.csv')
    bt['date'] = pd.to_datetime(bt['date']).dt.date
    rows = []
    for origin, g in bt.groupby('origin'):
        known = g.dropna(subset=['actual'])
        if known['date'].nunique() < 10:
            continue
        actual = {d: int(a) for d, a in known.drop_duplicates('date')[['date', 'actual']].values}
        for name, plan in link.FIXED.items():
            rows.append(dict(origin=origin, plan=name, **link.evaluate(actual, plan)))
    return pd.DataFrame(rows).groupby('plan').agg(mean_cost=('cost', 'mean'), mean_on_time_share=('on_time_share', 'mean'))


def main():
    checks = json.loads(BLS.read_text())['checks']
    assumed = {'regular_hourly_cost': link.costs['regular_hourly_cost'], 'temporary_hourly_cost': link.costs['temporary_hourly_cost']}
    real = {'regular_hourly_cost': checks['real_regular_employer_cost'], 'temporary_hourly_cost': checks['real_temp_bill_rate']}
    table = replay(assumed).join(replay(real), lsuffix='_assumed', rsuffix='_real')
    table = table.rename(columns={'mean_on_time_share_assumed': 'on_time_share'}).drop(columns='mean_on_time_share_real')
    for k, v in {**{f'assumed_{k}': v for k, v in assumed.items()}, **{f'real_{k}': v for k, v in real.items()}}.items():
        table[k] = v
    table.round(2).reset_index().to_csv(OUT, index=False)
    pd.set_option('display.width', 200)
    print(table.round(2).to_string())


if __name__ == '__main__':
    main()
