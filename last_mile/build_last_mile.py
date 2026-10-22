"""Part 4b: the last mile. How many delivery vans does each station need, and should it own or contract them?

Real, from the middle mile: every 2023 order, its delivery station and the day it reaches the station, for each
staffing plan (so late warehouses and late trucks move parcels to later days). Assumed (config.json): customer
locations, van size, shift, speed and costs.

For each staffing plan, station and day:
  1. group the day's parcels into stops (one per customer)
  2. route vans from the station with OR-Tools: van capacity, a 10 hour shift, fewest vans then shortest distance
  3. record vans and km
Then for each station, find the cheapest mix of owned vans (paid every day) and contracted vans (paid when used),
and compare it with handing every order to a parcel carrier.

Run from the repo root:
    .venv/bin/python last_mile/build_last_mile.py
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / 'middle_mile' / 'connected'))
import build_connected as mm  # noqa: E402

CONFIG = json.loads((HERE / 'config.json').read_text())
OUT = HERE / 'results'


def unit_hash(*parts):
    return int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()[:12], 16) / 16 ** 12


TRACTS = REPO / 'data/raw/census_tracts/2023_Gaz_tracts_national.txt'
POPULATION = REPO / 'data/raw/census_tracts/acs2022_tract_population.csv'  # from fetch_census_population.py
AREAS = REPO / 'data/raw/ors/delivery_areas.json'  # drive-time areas from fetch_road_matrix.py
_tracts = {}


def station_tracts(station):
    """Census tract centers in the station's delivery area (45 minute drive, or a radius without the ORS file), with each tract's share of the area's people
    (equal shares if the population file has not been downloaded)."""
    if station not in _tracts:
        t = pd.read_csv(TRACTS, sep='\t', usecols=[1, 6, 7], names=['geoid', 'lat', 'lng'], header=0, dtype={'geoid': str})
        s = mm.CONFIG['stations'][station]
        if AREAS.exists():  # inside the 45 minute drive area
            area = MplPath(json.loads(AREAS.read_text())[station])
            t = t[area.contains_points(t[['lng', 'lat']].to_numpy())]
        else:
            t = t[mm.haversine_km(s['lat'], s['lng'], t['lat'].to_numpy(), t['lng'].to_numpy()) <= CONFIG['delivery_radius_km'][station]]
        if POPULATION.exists():
            people = pd.read_csv(POPULATION, dtype={'geoid': str}).set_index('geoid')['population']
            t = t.assign(people=t['geoid'].map(people).fillna(0))
        else:
            t = t.assign(people=1)
        t = t[t['people'] > 0].sort_values('geoid')
        _tracts[station] = (t[['lat', 'lng']].to_numpy(), (t['people'].cumsum() / t['people'].sum()).to_numpy())
    return _tracts[station]


def customer_point(customer, station):
    """A fixed point for each customer: a census tract center near the station, picked with odds matching the
    tract's population; without the Census file, a point spread evenly over the delivery area."""
    if TRACTS.exists():
        points, cumulative = station_tracts(station)
        lat, lng = points[min(int(np.searchsorted(cumulative, unit_hash('tract', customer))), len(points) - 1)]
        return float(lat), float(lng)
    s = mm.CONFIG['stations'][station]
    radius = CONFIG['delivery_radius_km'][station] * math.sqrt(unit_hash('r', customer))
    angle = 2 * math.pi * unit_hash('a', customer)
    return (s['lat'] + radius * math.sin(angle) / 111.0,
            s['lng'] + radius * math.cos(angle) / (111.0 * math.cos(math.radians(s['lat']))))


FRED = REPO / 'data/processed/fred_benchmarks.json'  # from scripts/fetch_fred_benchmarks.py
_diesel = None


def km_cost(day=None):
    """Van cost per km: fuel at that week's real US diesel price (FRED) plus other running costs per km;
    the assumed flat cost per km if the FRED file is missing. Without a day, the 2023 average."""
    global _diesel
    if _diesel is None:
        values = json.loads(FRED.read_text())['series']['GASDESW']['values'] if FRED.exists() else {}
        _diesel = pd.Series(values, dtype=float).sort_index()
        _diesel.index = pd.to_datetime(_diesel.index)
    if _diesel.empty:
        return CONFIG['cost_per_km']
    week = _diesel[_diesel.index.year == 2023]
    price = week.mean() if day is None else _diesel[:pd.Timestamp(day)].iloc[-1]
    return CONFIG['fuel_gallons_per_km'] * price + CONFIG['other_cost_per_km']


ROADS = REPO / 'data/raw/ors/van_matrix.json'  # from fetch_road_matrix.py
_roads = None


def road(a, b):
    """Road km and drive minutes from a to b: OpenRouteService when fetched (traffic-free), otherwise
    1.3 x straight line distance at 35 km/h."""
    global _roads
    if _roads is None:
        _roads = {}
        if ROADS.exists():
            for m in json.loads(ROADS.read_text()).values():
                points = [tuple(p) for p in m['points']]
                for i, pa in enumerate(points):
                    for j, pb in enumerate(points):
                        if m['km'][i][j] is not None and m['minutes'][i][j] is not None:
                            _roads[pa, pb] = (m['km'][i][j], m['minutes'][i][j])
    if (a, b) in _roads:
        return _roads[a, b]
    km = CONFIG['road_factor'] * mm.haversine_km(a[0], a[1], b[0], b[1])
    return km, 60 * km / CONFIG['speed_kmh']


KM_COST = km_cost()  # 2023 average, used to compare routes


def split_stops(stops):
    """A stop bigger than one van becomes several van loads at the same point."""
    cap = CONFIG['van_capacity_units']
    out = []
    for point, units in stops:
        while units > cap:
            out.append((point, cap))
            units -= cap
        out.append((point, units))
    return out


def route_day(depot, stops):
    """Vans and km to serve the stops from the depot. Returns (vans, km, routes as lists of stop indexes)."""
    stops = split_stops(stops)
    if not stops:
        return 0, 0.0, []
    points = [depot] + [p for p, _ in stops]
    demand = [0] + [u for _, u in stops]
    n = len(points)
    legs = [[road(points[i], points[j]) for j in range(n)] for i in range(n)]
    km = [[k for k, _ in row] for row in legs]
    drive = [[m for _, m in row] for row in legs]
    service = [0] + [CONFIG['minutes_per_stop'] + CONFIG['minutes_per_unit'] * u for u in demand[1:]]
    # enough vans for the load and for the work time; spare vans cost a fixed fee, so the solver leaves them parked
    work = sum(service) + sum(drive[0][i] + drive[i][0] for i in range(1, n)) / 3
    vans = max(math.ceil(sum(demand) / CONFIG['van_capacity_units']), math.ceil(work / CONFIG['shift_minutes'])) + 3
    return _solve(points, demand, km, drive, service, vans)


def _solve(points, demand, km, drive, service, vans):
    n = len(points)
    manager = pywrapcp.RoutingIndexManager(n, vans, 0)
    routing = pywrapcp.RoutingModel(manager)
    cents = routing.RegisterTransitCallback(
        lambda i, j: int(round(100 * KM_COST * km[manager.IndexToNode(i)][manager.IndexToNode(j)])))
    routing.SetArcCostEvaluatorOfAllVehicles(cents)
    routing.SetFixedCostOfAllVehicles(100 * CONFIG['owned_van_cost_per_day'])  # fewest vans first
    load = routing.RegisterUnaryTransitCallback(lambda i: demand[manager.IndexToNode(i)])
    routing.AddDimensionWithVehicleCapacity(load, 0, [CONFIG['van_capacity_units']] * vans, True, 'load')
    minutes = routing.RegisterTransitCallback(lambda i, j: int(round(
        drive[manager.IndexToNode(i)][manager.IndexToNode(j)] + service[manager.IndexToNode(i)])))
    routing.AddDimension(minutes, 0, CONFIG['shift_minutes'], True, 'time')
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.time_limit.seconds = CONFIG['solver_seconds']
    solution = routing.SolveWithParameters(params)
    if solution is None:
        if vans >= n:
            raise RuntimeError(f'no route plan for {n - 1} stops even with one van per stop')
        return _solve(points, demand, km, drive, service, min(n, 2 * vans))  # not enough vans: allow more and retry
    routes, total_km = [], 0.0
    for v in range(vans):
        i, route = routing.Start(v), []
        while not routing.IsEnd(i):
            j = solution.Value(routing.NextVar(i))
            total_km += km[manager.IndexToNode(i)][manager.IndexToNode(j)]
            if manager.IndexToNode(i):
                route.append(manager.IndexToNode(i) - 1)
            i = j
        if route:
            routes.append(route)
    return len(routes), total_km, routes


def best_fleet(need, km_cost):
    """Cheapest number of owned vans when extra vans can be contracted on the days they are needed."""
    days = len(need)

    def cost(owned):
        return owned * CONFIG['owned_van_cost_per_day'] * days + sum(max(0, v - owned) for v in need) * CONFIG['contract_van_cost_per_day'] + km_cost

    owned = min(range(max(need) + 1), key=cost)
    return dict(owned_vans=owned, contract_van_days=int(sum(max(0, v - owned) for v in need)), cost=round(cost(owned)),
                cost_owning_for_peak=round(cost(max(need))), cost_all_contracted=round(cost(0)))


def plan_parcels():
    """Every order with its station and delivery day, for each staffing plan, from the middle mile."""
    net, orders, shares = mm.Network(), mm.load_orders(), mm.site_shares()
    stations = {k: v['population_millions'] for k, v in mm.CONFIG['stations'].items()}
    orders['site'] = [mm.weighted_pick(c, shares, 'site') for c in orders['customer']]
    orders['station'] = [mm.weighted_pick(c, stations, 'station') for c in orders['customer']]
    for name, plan in mm.CONFIG['staffing_plans'].items():
        _, _, detail = mm.evaluate_plan(name, plan, orders, net)
        yield name, detail.dropna(subset=['delivered'])


def main():
    OUT.mkdir(exist_ok=True)
    daily, fleets = [], []
    for plan, parcels in plan_parcels():
        parcels = parcels.assign(point=[customer_point(c, s) for c, s in zip(parcels['customer'], parcels['station'])])
        for (station, day), g in parcels.groupby(['station', 'delivered']):
            stops = g.groupby('customer').agg(point=('point', 'first'), units=('units', 'sum'))
            s = mm.CONFIG['stations'][station]
            vans, km, _ = route_day((s['lat'], s['lng']), list(zip(stops['point'], stops['units'])))
            daily.append(dict(plan=plan, station=station, date=day, parcels=len(g), stops=len(stops),
                              units=int(g['units'].sum()), vans=vans, km=round(km, 1), km_cost=round(km * km_cost(day), 2)))
        print(plan, 'routed', flush=True)
    daily = pd.DataFrame(daily)
    for (plan, station), g in daily.groupby(['plan', 'station']):
        days = pd.date_range(g['date'].min(), g['date'].max())  # vans run every day, so quiet days count too
        need = g.set_index(pd.to_datetime(g['date']))['vans'].reindex(days, fill_value=0).tolist()
        fleet = best_fleet(need, g['km_cost'].sum())
        carrier = CONFIG['carrier_cost_per_order'] * g['parcels'].sum() + CONFIG['carrier_cost_per_unit'] * g['units'].sum()
        fleets.append(dict(plan=plan, station=station, days=len(days), parcels=int(g['parcels'].sum()),
                           median_vans=float(pd.Series(need).median()), peak_vans=max(need), **fleet,
                           cost_per_parcel=round(fleet['cost'] / g['parcels'].sum(), 2), carrier_cost=round(carrier),
                           cheaper_option='vans' if fleet['cost'] < carrier else 'carrier'))
    fleets = pd.DataFrame(fleets)
    daily.to_csv(OUT / 'daily_vans.csv', index=False)
    fleets.to_csv(OUT / 'fleet_by_station.csv', index=False)
    plans = []
    for plan, g in fleets.groupby('plan'):
        d = daily[daily['plan'] == plan]
        per_van_day = d['parcels'].sum() / d['vans'].sum()
        van_day_cost = CONFIG['contract_van_cost_per_day'] + d['km_cost'].sum() / d['vans'].sum()
        carrier_per_order = g['carrier_cost'].sum() / g['parcels'].sum()
        plans.append(dict(plan=plan, parcels=int(g['parcels'].sum()), owned_vans=int(g['owned_vans'].sum()),
                          peak_vans=int(g['peak_vans'].sum()), contract_van_days=int(g['contract_van_days'].sum()),
                          cost=int(g['cost'].sum()), cost_owning_for_peak=int(g['cost_owning_for_peak'].sum()),
                          cost_all_contracted=int(g['cost_all_contracted'].sum()),
                          cost_per_parcel=round(g['cost'].sum() / g['parcels'].sum(), 2),
                          carrier_cost=int(g['carrier_cost'].sum()),
                          carrier_cost_per_parcel=round(g['carrier_cost'].sum() / g['parcels'].sum(), 2),
                          stations_cheaper_by_van=int((g['cheaper_option'] == 'vans').sum()),
                          orders_per_van_day=round(per_van_day, 1),
                          break_even_orders_per_van_day=round(van_day_cost / carrier_per_order, 1)))
    road((0.0, 0.0), (0.0, 0.0))  # loads the road table if it exists
    pairs = [(k / mm.haversine_km(a[0], a[1], b[0], b[1]), 60 * k / m)
             for (a, b), (k, m) in _roads.items() if m > 0 and mm.haversine_km(a[0], a[1], b[0], b[1]) > 1]
    roads = dict(source='OpenRouteService driving-car, no traffic', pairs=len(pairs),
                 median_road_to_straight=round(float(np.median([r for r, _ in pairs])), 2),
                 median_speed_kmh=round(float(np.median([v for _, v in pairs])), 1)) if pairs else None
    fuel = dict(source='FRED GASDESW, weekly US on-highway diesel', average_cost_per_km_2023=round(km_cost(), 3),
                assumed_cost_per_km_before=CONFIG['cost_per_km']) if FRED.exists() else None
    (OUT / 'summary.json').write_text(json.dumps(dict(evidence_status=CONFIG['evidence_status'], roads=roads, fuel=fuel, plans=plans), indent=2) + '\n')
    pd.set_option('display.width', 220)
    print(fleets.to_string(index=False))
    print(json.dumps(plans, indent=2))


if __name__ == '__main__':
    main()
