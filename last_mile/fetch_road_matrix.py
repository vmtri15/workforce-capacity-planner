"""Download delivery areas, road distances and drive times from OpenRouteService.

0. Delivery areas (isochrones): everywhere a van can reach within 45 minutes of each station. Customers are then
   placed inside these areas instead of inside a circle.
1. Vans (driving-car): between each delivery station and every customer location it serves, and between those
   locations, so the last mile routes on roads instead of 1.3 x straight line distance.
2. Trucks (driving-hgv): between the 11 places of the middle mile network, to check its assumed lane times.

Needs ORS_API_KEY in the project's .env (free: https://openrouteservice.org/dev/#/signup). Calls api.heigit.org, which
replaced api.openrouteservice.org in 2026 (the old address gets only 10% of the quota). The free plan allows
3,500 pairs per request and about 40 requests a minute, so requests are split into blocks and paced.
Writes data/raw/ors/delivery_areas.json, van_matrix.json and truck_lanes.json (gitignored). Run from the repo root,
after data/raw/census_tracts/ is in place:
    .venv/bin/python last_mile/fetch_road_matrix.py
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'ask_the_planner'))
import build_last_mile as lm  # noqa: E402
from planner_agent import load_env_file  # noqa: E402

OUT = REPO / 'data/raw/ors'
BLOCK = 50  # 50 x 50 = 2,500 pairs per request, under the 3,500 limit


def matrix(points, sources, destinations, profile, key):
    """Road km and minutes from each source to each destination. points are (lat, lng)."""
    body = json.dumps({'locations': [[lng, lat] for lat, lng in points], 'sources': sources, 'destinations': destinations,
                       'metrics': ['distance', 'duration'], 'units': 'km'}).encode()
    request = urllib.request.Request(f'https://api.heigit.org/openrouteservice/v2/matrix/{profile}', data=body,
                                     headers={'Authorization': key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read())
    time.sleep(1.6)  # stay under 40 requests a minute
    minutes = [[None if v is None else v / 60 for v in row] for row in result['durations']]
    return result['distances'], minutes


def delivery_areas(key):
    """One drive-time polygon per station, as [lng, lat] rings."""
    areas = {}
    for station, s in lm.mm.CONFIG['stations'].items():
        body = json.dumps({'locations': [[s['lng'], s['lat']]], 'range': [60 * lm.CONFIG['delivery_drive_minutes']],
                           'range_type': 'time'}).encode()
        request = urllib.request.Request('https://api.heigit.org/openrouteservice/v2/isochrones/driving-car', data=body,
                                         headers={'Authorization': key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=120) as response:
            areas[station] = json.loads(response.read())['features'][0]['geometry']['coordinates'][0]
        time.sleep(3.5)  # the isochrone API allows 20 requests a minute
        print(f'{station}: delivery area with {len(areas[station])} corners', flush=True)
    return areas


def full_matrix(points, profile, key):
    n = len(points)
    km = [[None] * n for _ in range(n)]
    minutes = [[None] * n for _ in range(n)]
    for i0 in range(0, n, BLOCK):
        for j0 in range(0, n, BLOCK):
            rows, cols = list(range(i0, min(n, i0 + BLOCK))), list(range(j0, min(n, j0 + BLOCK)))
            d, t = matrix(points, rows, cols, profile, key)
            for a, i in enumerate(rows):
                for b, j in enumerate(cols):
                    km[i][j], minutes[i][j] = d[a][b], t[a][b]
    return km, minutes


def main():
    load_env_file()
    key = os.environ.get('ORS_API_KEY')
    if not key:
        sys.exit('ORS_API_KEY is not set. Add it to the .env file in the project root.')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'delivery_areas.json').write_text(json.dumps(delivery_areas(key)))
    lm._tracts.clear()  # customer places now come from the new areas
    orders, stations = lm.mm.load_orders(), lm.mm.CONFIG['stations']
    weights = {k: v['population_millions'] for k, v in stations.items()}
    customers = {c: lm.mm.weighted_pick(c, weights, 'station') for c in orders['customer'].unique()}
    vans = {}
    for station, s in stations.items():
        points = [(s['lat'], s['lng'])] + sorted({lm.customer_point(c, st) for c, st in customers.items() if st == station})
        km, minutes = full_matrix(points, 'driving-car', key)
        vans[station] = dict(points=points, km=km, minutes=minutes)
        print(f'{station}: {len(points)} places, {len(points) ** 2:,} pairs', flush=True)
    (OUT / 'van_matrix.json').write_text(json.dumps(vans))
    places = {**lm.mm.CONFIG['sites'], **lm.mm.CONFIG['sort_centers'], **stations}
    names = sorted(places)
    km, minutes = full_matrix([(places[p]['lat'], places[p]['lng']) for p in names], 'driving-hgv', key)
    (OUT / 'truck_lanes.json').write_text(json.dumps(dict(places=names, km=km, minutes=minutes), indent=1))
    print(f'Wrote {OUT.relative_to(REPO)}/van_matrix.json and truck_lanes.json')


if __name__ == '__main__':
    main()
