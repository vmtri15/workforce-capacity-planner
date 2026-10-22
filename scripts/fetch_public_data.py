"""Download every public input the project needs into data/raw/ (gitignored), in one step.

No key needed:
  * the 2023 footwear warehouse orders (Mendeley Data, CC BY 4.0): Customer_Order, Product, Picking_Wave
  * UCI Online Retail II (the 2011 retail history behind the planning database)
  * BLS QCEW 2025 Q4 for warehousing (NAICS 493) and couriers (492)
  * the 2023 Census Gazetteer census tract file
Needs a free key in .env (each step is skipped, with a message, when its key is missing):
  * CENSUS_API_KEY: County Business Patterns for the four site counties, then tract populations
  * BLS_API_KEY, NOAA_TOKEN, FRED_API_KEY, ORS_API_KEY: the real-data checks (their own fetch scripts)

Files that already exist are kept; pass --force to download again. Run from the repo root:
    .venv/bin/python scripts/fetch_public_data.py
"""
import argparse
import io
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
sys.path.insert(0, str(ROOT / 'ask_the_planner'))
from planner_agent import load_env_file  # noqa: E402

MENDELEY = 'https://data.mendeley.com/public-files/datasets/pf2w725pw3/files/{}/file_downloaded'
FOOTWEAR = {'Customer_Order.csv': 'd08bf859-1fc8-4469-922f-13be7516a30c', 'Product.csv': '0be2b552-260d-43f2-9e36-fb4a3e71f85d',
            'Picking_Wave.csv': 'dff20565-5df8-4b77-ad9d-8b034069bcca'}
CBP_COUNTIES = {'cook': ('17', '031'), 'dupage': ('17', '043'), 'will': ('17', '197'), 'kenosha': ('55', '059')}
KEYED_STEPS = [  # (key in .env, script, file it writes)
    ('CENSUS_API_KEY', 'last_mile/fetch_census_population.py', 'data/raw/census_tracts/acs2022_tract_population.csv'),
    ('BLS_API_KEY', 'scripts/fetch_bls_benchmarks.py', 'data/processed/bls_2023_benchmarks.json'),
    ('NOAA_TOKEN', 'middle_mile/connected/fetch_noaa_weather.py', 'data/raw/noaa/ghcnd_2023.csv'),
    ('FRED_API_KEY', 'scripts/fetch_fred_benchmarks.py', 'data/processed/fred_benchmarks.json'),
    ('ORS_API_KEY', 'last_mile/fetch_road_matrix.py', 'data/raw/ors/van_matrix.json'),
]


def download(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'workforce-capacity-planner (portfolio project)'})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f'  wrote {path.relative_to(ROOT)} ({len(data) / 1e6:.1f} MB)', flush=True)


def need(path, force):
    if path.exists() and not force:
        print(f'  have {path.relative_to(ROOT)}', flush=True)
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='download again even if the file exists')
    args = parser.parse_args()
    load_env_file()

    print('2023 footwear orders (Mendeley Data)')
    for name, file_id in FOOTWEAR.items():
        if need(RAW / 'warehouse_picking' / name, args.force):
            save(RAW / 'warehouse_picking' / name, download(MENDELEY.format(file_id)))

    print('UCI Online Retail II')
    if need(RAW / 'uci/online_retail_II.xlsx', args.force):
        archive = zipfile.ZipFile(io.BytesIO(download('https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip')))
        save(RAW / 'uci/online_retail_II.xlsx', archive.read('online_retail_II.xlsx'))

    print('BLS QCEW 2025 Q4')
    for naics in ('493', '492'):
        if need(RAW / f'bls/workforce-qcew-2025q4-{naics}.csv', args.force):
            save(RAW / f'bls/workforce-qcew-2025q4-{naics}.csv', download(f'https://data.bls.gov/cew/data/api/2025/4/industry/{naics}.csv'))

    print('Census Gazetteer tracts')
    if need(RAW / 'census_tracts/2023_Gaz_tracts_national.txt', args.force):
        archive = zipfile.ZipFile(io.BytesIO(download(
            'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_tracts_national.zip')))
        save(RAW / 'census_tracts/2023_Gaz_tracts_national.txt', archive.read('2023_Gaz_tracts_national.txt'))

    print('Census County Business Patterns 2023 (warehousing, the four site counties)')
    key = os.environ.get('CENSUS_API_KEY')
    for county, (state, code) in CBP_COUNTIES.items():
        path = RAW / f'census/cbp_2023_{county}_493.json'
        if not need(path, args.force):
            continue
        if not key:
            print('  skipped: add CENSUS_API_KEY to .env', flush=True)
            break
        query = urllib.parse.urlencode({'get': 'NAME,NAICS2017,NAICS2017_LABEL,ESTAB,EMP,PAYANN', 'for': f'county:{code}',
                                        'in': f'state:{state}', 'NAICS2017': '493', 'key': key})
        save(path, download(f'https://api.census.gov/data/2023/cbp?{query}'))

    failed = []
    for env_key, script, output in KEYED_STEPS:
        print(script)
        if not need(ROOT / output, args.force):
            continue
        if not os.environ.get(env_key):
            print(f'  skipped: add {env_key} to .env', flush=True)
            continue
        if subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT).returncode:
            failed.append(script)  # usually a busy or down API: the other steps still run
    if failed:
        print('Some steps failed, often because an API was briefly down. Run this again later; finished files are kept:')
        print('\n'.join(f'  {s}' for s in failed))
        sys.exit(1)
    print('Done. Next: build the database and run the models (README, "Run it yourself").')


if __name__ == '__main__':
    main()
