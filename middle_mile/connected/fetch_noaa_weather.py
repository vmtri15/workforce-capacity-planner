"""Download 2023 daily weather (snowfall, precipitation, minimum temperature) at the airport nearest each place
in the connected network, from NOAA's Climate Data Online API (GHCN-Daily, metric units).

Needs NOAA_TOKEN in the project's .env (free: https://www.ncdc.noaa.gov/cdo-web/token).
Writes data/raw/noaa/ghcnd_2023.csv (gitignored). Run from the repo root:
    .venv/bin/python middle_mile/connected/fetch_noaa_weather.py
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'ask_the_planner'))
from planner_agent import load_env_file  # noqa: E402

CONFIG = json.loads((HERE / 'config.json').read_text())
OUT = REPO / 'data/raw/noaa/ghcnd_2023.csv'


def fetch_station(station, token):
    rows, offset = [], 1
    while True:
        query = urllib.parse.urlencode({'datasetid': 'GHCND', 'stationid': f'GHCND:{station}', 'startdate': '2023-01-01',
                                        'enddate': '2023-12-31', 'datatypeid': ['SNOW', 'PRCP', 'TMIN'], 'units': 'metric',
                                        'limit': 1000, 'offset': offset}, doseq=True)
        request = urllib.request.Request(f'https://www.ncei.noaa.gov/cdo-web/api/v2/data?{query}', headers={'token': token})
        with urllib.request.urlopen(request, timeout=60) as response:
            page = json.loads(response.read() or b'{}')
        rows += page.get('results', [])
        count = page.get('metadata', {}).get('resultset', {}).get('count', 0)
        offset += 1000
        time.sleep(0.25)  # the API allows 5 requests a second
        if offset > count:
            return rows


def main():
    load_env_file()
    token = os.environ.get('NOAA_TOKEN')
    if not token:
        sys.exit('NOAA_TOKEN is not set. Add it to the .env file in the project root.')
    stations = sorted(set(CONFIG['weather']['stations'].values()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['station', 'date', 'datatype', 'value'])
        for station in stations:
            rows = fetch_station(station, token)
            writer.writerows((station, r['date'][:10], r['datatype'], r['value']) for r in rows)
            print(f'{station}: {len(rows):,} values', flush=True)
    print(f'Wrote {OUT.relative_to(REPO)}')


if __name__ == '__main__':
    main()
