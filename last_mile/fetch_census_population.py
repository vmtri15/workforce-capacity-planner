"""Download the population of every census tract in the six station states (ACS 2022 5-year, table B01003).

Needs CENSUS_API_KEY in the project's .env (free: https://api.census.gov/data/key_signup.html).
Writes data/raw/census_tracts/acs2022_tract_population.csv (gitignored). Run from the repo root:
    .venv/bin/python last_mile/fetch_census_population.py
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'ask_the_planner'))
from planner_agent import load_env_file  # noqa: E402  reads .env without overriding the shell

STATES = {'17': 'IL', '18': 'IN', '26': 'MI', '27': 'MN', '29': 'MO', '55': 'WI'}
OUT = REPO / 'data/raw/census_tracts/acs2022_tract_population.csv'


def main():
    load_env_file()
    key = os.environ.get('CENSUS_API_KEY')
    if not key:
        sys.exit('CENSUS_API_KEY is not set. Add it to the .env file in the project root.')
    rows = []
    for fips, name in STATES.items():
        query = urllib.parse.urlencode({'get': 'B01003_001E', 'for': 'tract:*', 'in': f'state:{fips}', 'key': key})
        with urllib.request.urlopen(f'https://api.census.gov/data/2022/acs/acs5?{query}', timeout=60) as response:
            header, *data = json.loads(response.read())
        col = {c: i for i, c in enumerate(header)}
        for r in data:
            rows.append((r[col['state']] + r[col['county']] + r[col['tract']], max(0, int(r[col['B01003_001E']]))))
        print(f'{name}: {len(data):,} tracts', flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['geoid', 'population'])
        writer.writerows(rows)
    print(f'Wrote {len(rows):,} tracts to {OUT.relative_to(REPO)}')


if __name__ == '__main__':
    main()
