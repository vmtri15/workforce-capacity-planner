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

import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / 'middle_mile' / 'connected'))
import build_connected as mm  # noqa: E402

CONFIG = json.loads((HERE / 'config.json').read_text())
OUT = HERE / 'results'


def unit_hash(*parts):
    return int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()[:12], 16) / 16 ** 12


def customer_point(customer, station):
    """A fixed point for each customer, spread evenly over the station's delivery area."""
    s = mm.CONFIG['stations'][station]
    radius = CONFIG['delivery_radius_km'][station] * math.sqrt(unit_hash('r', customer))
    angle = 2 * math.pi * unit_hash('a', customer)
    return (s['lat'] + radius * math.sin(angle) / 111.0,
            s['lng'] + radius * math.cos(angle) / (111.0 * math.cos(math.radians(s['lat']))))


def road_km(a, b):
    return CONFIG['road_factor'] * mm.haversine_km(a[0], a[1], b[0], b[1])


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
    km = [[road_km(points[i], points[j]) for j in range(n)] for i in range(n)]
    service = [0] + [CONFIG['minutes_per_stop'] + CONFIG['minutes_per_unit'] * u for u in demand[1:]]
    # enough vans for the load and for the work time; spare vans cost a fixed fee, so the solver leaves them parked
    work = sum(service) + sum(2 * 60 * km[0][i] / CONFIG['speed_kmh'] for i in range(1, n)) / 3
    vans = max(math.ceil(sum(demand) / CONFIG['van_capacity_units']), math.ceil(work / CONFIG['shift_minutes'])) + 3
    return _solve(points, demand, km, service, vans)


def _solve(points, demand, km, service, vans):
    n = len(points)
    manager = pywrapcp.RoutingIndexManager(n, vans, 0)
    routing = pywrapcp.RoutingModel(manager)
    cents = routing.RegisterTransitCallback(
        lambda i, j: int(round(100 * CONFIG['cost_per_km'] * km[manager.IndexToNode(i)][manager.IndexToNode(j)])))
    routing.SetArcCostEvaluatorOfAllVehicles(cents)
    routing.SetFixedCostOfAllVehicles(100 * CONFIG['owned_van_cost_per_day'])  # fewest vans first
    load = routing.RegisterUnaryTransitCallback(lambda i: demand[manager.IndexToNode(i)])
    routing.AddDimensionWithVehicleCapacity(load, 0, [CONFIG['van_capacity_units']] * vans, True, 'load')
    minutes = routing.RegisterTransitCallback(lambda i, j: int(round(
        60 * km[manager.IndexToNode(i)][manager.IndexToNode(j)] / CONFIG['speed_kmh'] + service[manager.IndexToNode(i)])))
    routing.AddDimension(minutes, 0, CONFIG['shift_minutes'], True, 'time')
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.time_limit.seconds = CONFIG['solver_seconds']
    solution = routing.SolveWithParameters(params)
    if solution is None:
        if vans >= n:
            raise RuntimeError(f'no route plan for {n - 1} stops even with one van per stop')
        return _solve(points, demand, km, service, min(n, 2 * vans))  # not enough vans: allow more and retry
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
                              units=int(g['units'].sum()), vans=vans, km=round(km, 1)))
        print(plan, 'routed', flush=True)
    daily = pd.DataFrame(daily)
    for (plan, station), g in daily.groupby(['plan', 'station']):
        days = pd.date_range(g['date'].min(), g['date'].max())  # vans run every day, so quiet days count too
        need = g.set_index(pd.to_datetime(g['date']))['vans'].reindex(days, fill_value=0).tolist()
        fleet = best_fleet(need, g['km'].sum() * CONFIG['cost_per_km'])
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
        van_day_cost = CONFIG['contract_van_cost_per_day'] + d['km'].sum() * CONFIG['cost_per_km'] / d['vans'].sum()
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
    (OUT / 'summary.json').write_text(json.dumps(dict(evidence_status=CONFIG['evidence_status'], plans=plans), indent=2) + '\n')
    pd.set_option('display.width', 220)
    print(fleets.to_string(index=False))
    print(json.dumps(plans, indent=2))


if __name__ == '__main__':
    main()
