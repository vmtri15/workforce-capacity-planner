"""Check the staffing model's pay and turnover assumptions against 2023 BLS data.

Series (BLS Public Data API v2, needs BLS_API_KEY in .env):
  CEU4349300003  Warehousing and storage, average hourly earnings, all employees (not seasonally adjusted)
  CEU4349300008  Warehousing and storage, average hourly earnings, production and nonsupervisory employees
  JTU480099000000000QUR  Transportation, warehousing and utilities, quits rate (JOLTS, % of employment a month)
  JTU480099000000000JOR  Transportation, warehousing and utilities, job openings rate (JOLTS)
  CMU2010000520000D  Private industry, production, transportation and material moving: total compensation per hour (ECEC)
  CMU2020000520000D  The same occupations: wages and salaries per hour (ECEC)
  CEU6056132003      Temporary help services, average hourly earnings, all employees
Writes data/processed/bls_2023_benchmarks.json. Run from the repo root:
    .venv/bin/python scripts/fetch_bls_benchmarks.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ask_the_planner'))
from planner_agent import load_env_file  # noqa: E402

SERIES = {'CEU4349300003': 'hourly_earnings_all_employees', 'CEU4349300008': 'hourly_earnings_production_workers',
          'JTU480099000000000QUR': 'quits_rate_percent', 'JTU480099000000000JOR': 'job_openings_rate_percent',
          'CMU2010000520000D': 'employer_cost_per_hour_total', 'CMU2020000520000D': 'employer_cost_per_hour_wages',
          'CEU6056132003': 'temp_help_hourly_earnings'}
AGENCY_MARKUP = 1.5  # assumed: what a staffing agency bills over the temp's pay (taxes, insurance, margin); not in BLS data
OUT = ROOT / 'data/processed/bls_2023_benchmarks.json'
COSTS = ROOT / 'config/staffing_cost_scenarios.json'


def fetch(key):
    body = json.dumps({'seriesid': list(SERIES), 'startyear': '2023', 'endyear': '2023', 'registrationkey': key}).encode()
    request = urllib.request.Request('https://api.bls.gov/publicAPI/v2/timeseries/data/', data=body,
                                     headers={'Content-type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read())
    if result.get('status') != 'REQUEST_SUCCEEDED':
        sys.exit(f"BLS request failed: {result.get('message')}")
    return {s['seriesID']: sorted((d['period'], float(d['value'])) for d in s['data'] if d['period'][0] in 'MQ' and d['period'] not in ('M13', 'Q05'))
            for s in result['Results']['series']}


def main():
    load_env_file()
    if not os.environ.get('BLS_API_KEY'):
        sys.exit('BLS_API_KEY is not set. Add it to the .env file in the project root.')
    data = fetch(os.environ['BLS_API_KEY'])
    costs = json.loads(COSTS.read_text())
    series = {}
    for sid, name in SERIES.items():
        values = [v for _, v in data[sid]]
        series[name] = dict(series_id=sid, months=len(values), average_2023=round(sum(values) / len(values), 2),
                            january=values[0], december=values[-1], monthly=dict(data[sid]))
    quits = series['quits_rate_percent']['average_2023'] / 100
    multiplier = series['employer_cost_per_hour_total']['average_2023'] / series['employer_cost_per_hour_wages']['average_2023']
    team = costs['base_workers']
    result = dict(
        source='U.S. Bureau of Labor Statistics, Current Employment Statistics and JOLTS, 2023, national',
        series=series,
        checks=dict(
            assumed_regular_hourly_cost=costs['regular_hourly_cost'],
            real_production_worker_hourly_earnings=series['hourly_earnings_production_workers']['average_2023'],
            assumed_temporary_hourly_cost=costs['temporary_hourly_cost'],
            quits_per_year_share_of_team=round(quits * 12, 2),
            expected_quits_per_year_in_a_team_of=team,
            expected_quits_per_year=round(quits * 12 * team, 1),
            months_between_quits_in_the_team=round(1 / (quits * team), 1),
            employer_cost_multiplier=round(multiplier, 3),
            real_regular_employer_cost=round(series['hourly_earnings_production_workers']['average_2023'] * multiplier, 2),
            real_temp_pay=series['temp_help_hourly_earnings']['average_2023'],
            assumed_agency_markup=AGENCY_MARKUP,
            real_temp_bill_rate=round(series['temp_help_hourly_earnings']['average_2023'] * AGENCY_MARKUP, 2),
            note='Earnings are wages before benefits and payroll taxes; the employer cost multiplier (total compensation over '
                 'wages, ECEC) turns them into employer costs. '
                 'Quits are national for transportation, warehousing and utilities, not these sites.'),
    )
    OUT.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['checks'], indent=2))


if __name__ == '__main__':
    main()
