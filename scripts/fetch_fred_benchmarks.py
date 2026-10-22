"""Pull 2022 and 2023 economic context from FRED (Federal Reserve Bank of St. Louis) for every part of the series.

Needs FRED_API_KEY in the project's .env (free: https://fredaccount.stlouisfed.org/apikey).
Writes data/processed/fred_benchmarks.json: each series' 2023 average, its change from 2022, and the raw values.
The weekly diesel price is also used by last_mile/build_last_mile.py for van fuel costs. Run from the repo root:
    .venv/bin/python scripts/fetch_fred_benchmarks.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ask_the_planner'))
from planner_agent import load_env_file  # noqa: E402

OUT = ROOT / 'data/processed/fred_benchmarks.json'
SERIES = {  # id: (part of the series, plain name, unit)
    'RSXFS': ('forecast', 'US retail sales, excluding food services', 'million dollars a month'),
    'ECOMPCTSA': ('forecast', 'Online share of US retail sales', 'percent'),
    'MRTSSM4482USN': ('forecast', 'US shoe store sales', 'million dollars a month'),
    'RETAILIRSA': ('inventory', 'US retailers: inventories to sales ratio', 'months of sales held in stock'),
    'CES4349300001': ('staffing', 'US warehousing and storage employment', 'thousand jobs'),
    'CHIC917URN': ('staffing', 'Chicago metro unemployment rate', 'percent'),
    'PCU493110493110': ('staffing', 'Producer price index, general warehousing and storage', 'index'),
    'GASDESW': ('transport', 'US on-highway diesel price', 'dollars a gallon'),
    'FRGSHPUSM649NCIS': ('transport', 'Cass freight shipments index', 'index'),
    'TRUCKD11': ('transport', 'ATA truck tonnage index', 'index'),
}


def observations(series_id, key):
    query = urllib.parse.urlencode({'series_id': series_id, 'api_key': key, 'file_type': 'json',
                                    'observation_start': '2022-01-01', 'observation_end': '2024-03-31'})
    with urllib.request.urlopen(f'https://api.stlouisfed.org/fred/series/observations?{query}', timeout=60) as response:
        rows = json.loads(response.read())['observations']
    return pd.Series({r['date']: float(r['value']) for r in rows if r['value'] != '.'})


def demand_lead(shoe_values):
    """Correlation of the warehouse's 2023 monthly units with US shoe store sales 0 to 4 months later.
    Only 10 months, so a hint at most."""
    lines = pd.read_csv(ROOT / 'data/raw/warehouse_picking/Customer_Order.csv', sep=';', encoding='utf-8-sig')
    units = lines.groupby(pd.to_datetime(lines['creationDate'], format='%d/%m/%Y %H:%M').dt.to_period('M'))['quantity (units)'].sum()
    shoes = pd.Series(shoe_values)
    shoes.index = pd.PeriodIndex(pd.to_datetime(shoes.index), freq='M')
    return {f'{lead}_months_later': round(float(units.corr(pd.Series(shoes.reindex(units.index + lead).to_numpy(), index=units.index))), 2)
            for lead in range(5)} | {'months': int(len(units))}


def main():
    load_env_file()
    key = os.environ.get('FRED_API_KEY')
    if not key:
        sys.exit('FRED_API_KEY is not set. Add it to the .env file in the project root.')
    result = {}
    for series_id, (part, name, unit) in SERIES.items():
        s = observations(series_id, key)
        y22, y23 = s[s.index.str.startswith('2022')], s[s.index.str.startswith('2023')]
        result[series_id] = dict(part=part, name=name, unit=unit, average_2022=round(y22.mean(), 3),
                                 average_2023=round(y23.mean(), 3), change_2023_vs_2022=round(y23.mean() / y22.mean() - 1, 4),
                                 first_2023=y23.iloc[0], last_2023=y23.iloc[-1], values=s.round(3).to_dict())
        print(f"{series_id:18} {name}: 2023 average {y23.mean():,.2f} {unit} ({y23.mean() / y22.mean() - 1:+.1%} vs 2022)", flush=True)
    OUT.write_text(json.dumps(dict(source='FRED, Federal Reserve Bank of St. Louis', series=result,
                                   demand_vs_shoe_stores=demand_lead(result['MRTSSM4482USN']['values'])), indent=1) + '\n')
    print(f'Wrote {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
