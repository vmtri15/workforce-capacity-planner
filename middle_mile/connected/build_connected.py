"""Part 3b: the middle mile for the planner's own network.

Real, from the planner: the 2023 orders (time, customer, units), the site shares, and the two staffing
plans in DECISION_ANSWER.md (6 workers or 10 workers, up to 2 overtime hours). The planner's own service
model decides on which day each order is finished. That day sets when the parcel can leave the site, so
a staffing decision flows straight into the middle mile.

Assumed (config.json): the Midwest network, which customer goes where, truck schedules and speed, the
delivery promise and the truck delays. Costs are hypothetical units.

For each staffing plan:
  1. finish each order with the planner's service model (first in, first out)
  2. route each parcel site -> sort center -> delivery station and compare delivery with its promise
  3. add random truck delays and find the parcels that trucks, not the warehouse, made late
  4. rank trucks by the late parcels they cause, and test the cheapest recovery on each at risk truck

Run from the repo root, after the planner's data is in place:
    .venv/bin/python middle_mile/connected/build_connected.py
"""
import csv
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(HERE.parent / 'scripts'))
from workforce_planner.cost_policy import make_policy  # noqa: E402
from workforce_planner.service_scenarios import deadline, simulate  # noqa: E402
from build_journeys import next_departure  # noqa: E402
from evaluate_recovery import cheapest  # noqa: E402
from prep_parcels import haversine_km  # noqa: E402

CONFIG = json.loads((HERE / 'config.json').read_text())
ORDERS_CSV = REPO / 'data/raw/warehouse_picking/Customer_Order.csv'
DB = REPO / 'data/workforce_planner.db'
OUT = HERE / 'results'
HOUR = pd.Timedelta(hours=1)
RATE = 40  # units per productive hour, the planner's base case


def load_orders():
    orders = {}
    with ORDERS_CSV.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle, delimiter=';'):
            o = orders.setdefault(row['orderNumber'], dict(order_id=row['orderNumber'], customer=row['codCustomer'].strip(),
                                                           created=datetime.strptime(row['creationDate'], '%d/%m/%Y %H:%M'), units=0))
            o['units'] += int(row['quantity (units)'])
    return pd.DataFrame(orders.values()).sort_values(['created', 'order_id']).reset_index(drop=True)


def site_shares():
    with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as c:
        return dict(c.execute('SELECT site_id, allocation_share FROM sites').fetchall())


def weighted_pick(key, weights, salt):
    """The same key always gets the same choice; choices are spread in proportion to the weights."""
    u = int(hashlib.sha256(f'{salt}:{key}'.encode()).hexdigest()[:12], 16) / 16 ** 12
    total, running = sum(weights.values()), 0.0
    for name in sorted(weights):
        running += weights[name] / total
        if u < running:
            return name
    return sorted(weights)[-1]


def fifo_completion(order_units, done_by_day):
    """Completion day of each order, first in first out. Orders never finished get None."""
    ends = np.cumsum(order_units)
    days = [d for d, _ in done_by_day]
    done = np.cumsum([n for _, n in done_by_day])
    idx = np.searchsorted(done, ends, side='left')
    return [days[i] if i < len(days) else None for i in idx]


def run_staffing(orders, plan):
    """Finish the orders with the planner's service model. Returns completion days and labor cost."""
    fw = json.loads((REPO / 'config/footwear_scenarios.json').read_text())
    costs = json.loads((REPO / 'config/staffing_cost_scenarios.json').read_text())
    workers = costs['base_workers'] + plan['extra_workers']
    demand = orders.groupby(orders['created'].dt.date)['units'].sum().astype(int).to_dict()
    policy = make_policy(workers, 0, RATE, plan['overtime_hours'], plan['temp_workers'], 1, fw, costs)
    summary, rows = simulate(demand, workers, 0, RATE, costs['service_operating_days'], fw, policy)
    done_by_day = [(datetime.fromisoformat(r['date']).date(), r['completed_on_time'] + r['completed_late']) for r in rows]
    labor = sum(r['regular_cost'] + r['overtime_cost'] + r['temporary_cost'] for r in rows)
    labor += policy.outstanding_shifts() * fw['paid_hours'] * costs['temporary_hourly_cost']
    return fifo_completion(orders['units'].to_numpy(), done_by_day), labor, summary['on_time_unit_share']


TRUCK_ROADS = REPO / 'data/raw/ors/truck_lanes.json'  # truck drive times, from last_mile/fetch_road_matrix.py


class Network:
    def __init__(self, config=CONFIG):
        self.c = config
        self.places = {**config['sites'], **config['sort_centers'], **config['stations']}
        self.hours = {}
        self.roads = None
        if TRUCK_ROADS.exists():
            r = json.loads(TRUCK_ROADS.read_text())
            i = {p: n for n, p in enumerate(r['places'])}
            self.roads = {(a, b): r['minutes'][i[a]][i[b]] / 60 for a in i for b in i if r['minutes'][i[a]][i[b]] is not None}

    def km(self, a, b):
        p, q = self.places[a], self.places[b]
        return float(haversine_km(p['lat'], p['lng'], q['lat'], q['lng']))

    def drive_hours(self, a, b):
        """Truck drive time: OpenRouteService's truck route (no traffic) when fetched, otherwise straight line at the
        configured speed. The delivery promise still uses straight line distance, like a carrier's zone chart."""
        if self.roads and (a, b) in self.roads:
            return self.roads[a, b]
        return self.km(a, b) / self.c['truck_speed_kmh']

    def lane_time(self, lane):
        if lane not in self.hours:
            self.hours[lane] = (self.c['loading_hours'] + self.drive_hours(*lane)) * HOUR
        return self.hours[lane]

    def promise(self, created, site, station):
        weekdays = [0, 1, 2, 3, 4]
        processing = deadline(created.date(), self.c['promise']['processing_operating_days'], weekdays)
        transit = 1 if self.km(site, station) <= self.c['promise']['next_day_within_km'] else 2
        return processing + timedelta(days=transit)

    def deliver(self, ready, site, station, delay=None):
        """Delivery date and the two trucks (lane, departure) the parcel rides."""
        sc = self.c['stations'][station]['sort_center']
        leg1 = (site, sc)
        dep1 = next_departure(ready, self.c['site_departures'])
        arr1 = dep1 + self.lane_time(leg1) + (delay((leg1, dep1)) if delay else 0.0) * HOUR
        leg2 = (sc, station)
        dep2 = next_departure(arr1 + self.c['sort_hours'] * HOUR, self.c['sort_center_departures'])
        arr2 = dep2 + self.lane_time(leg2) + (delay((leg2, dep2)) if delay else 0.0) * HOUR
        cutoff = arr2.normalize() + self.c['station_cutoff_hour'] * HOUR
        delivered = arr2.date() if arr2 <= cutoff else arr2.date() + timedelta(days=1)
        return delivered, [(leg1, dep1), (leg2, dep2)]


WEATHER = REPO / 'data/raw/noaa/ghcnd_2023.csv'  # from fetch_noaa_weather.py


def weather_slowdown(config=CONFIG):
    """Share of driving speed lost at each place on each day, from NOAA snow and rain. Empty without the file."""
    if not WEATHER.exists():
        return {}
    w, cut = config['weather'], config['weather']['speed_reduction']
    days = pd.read_csv(WEATHER).pivot_table(index=['station', 'date'], columns='datatype', values='value').fillna(0)
    by_station = {}
    for (station, day), r in days.iterrows():
        loss = (cut['heavy_snow'] if r.get('SNOW', 0) >= w['heavy_snow_mm'] else cut['light_snow'] if r.get('SNOW', 0) > 0
                else cut['heavy_rain'] if r.get('PRCP', 0) >= w['heavy_rain_mm'] else 0.0)
        by_station[station, pd.Timestamp(day).date()] = loss
    return {(place, day): loss for place, station in w['stations'].items() for (s, day), loss in by_station.items() if s == station}


def truck_delay(config=CONFIG, net=None, weather=True):
    """Arrival delay in hours for any truck, the same every run for the same truck: a random delay, plus the extra
    driving time when snow or heavy rain at either end of the lane slows the trucks that day."""
    d, cache = config['delays'], {}
    slowdown = weather_slowdown(config) if weather and net is not None else {}

    def delay(truck):
        if truck not in cache:
            (a, b), dep = truck
            seed = int(hashlib.sha256(f"{d['seed']}|{a}|{b}|{dep.isoformat()}".encode()).hexdigest()[:12], 16)
            cache[truck] = d['median_hours'] * float(np.exp(d['sigma'] * np.random.default_rng(seed).standard_normal()))
            loss = max(slowdown.get((a, dep.date()), 0.0), slowdown.get((b, dep.date()), 0.0))
            if loss:
                cache[truck] += net.drive_hours(a, b) * (1 / (1 - loss) - 1)
        return cache[truck]
    return delay


def with_overrides(delay, overrides):
    return lambda truck: overrides[truck] if truck in overrides else delay(truck)


def evaluate_plan(name, plan, orders, net):
    completion, labor, on_time_units = run_staffing(orders, plan)
    o = orders.assign(completed=completion)
    unfinished = int(o['completed'].isna().sum())
    o = o.dropna(subset=['completed']).reset_index(drop=True)
    ready_hour = net.c['ready_hour'] * HOUR
    o['ready'] = [max(pd.Timestamp(d) + ready_hour, pd.Timestamp(c)) for d, c in zip(o['completed'], o['created'])]
    o['promise'] = [net.promise(c, s, t) for c, s, t in zip(o['created'], o['site'], o['station'])]

    base = [net.deliver(r, s, t) for r, s, t in zip(o['ready'], o['site'], o['station'])]
    o['late_without_truck_delays'] = [d > p for (d, _), p in zip(base, o['promise'])]
    delay = truck_delay(net.c, net)
    delayed = [net.deliver(r, s, t, delay) for r, s, t in zip(o['ready'], o['site'], o['station'])]
    calm = truck_delay(net.c, net, weather=False)  # the same random delays without the weather, to measure its share
    late_if_calm = [net.deliver(r, s, t, calm)[0] > p for r, s, t, p in zip(o['ready'], o['site'], o['station'], o['promise'])]
    o['late_with_truck_delays'] = [d > p for (d, _), p in zip(delayed, o['promise'])]
    o['delivered'] = [d for d, _ in delayed]  # the day the station hands the parcel to a van (last_mile/ uses it)
    o['late_if_calm'] = late_if_calm
    truck_late = o['late_with_truck_delays'] & ~o['late_without_truck_delays']

    # each truck's own effect: late parcels that are on time once only that truck's delay is removed
    on_truck = defaultdict(list)
    for i, (_, trucks) in enumerate(delayed):
        for t in trucks:
            on_truck[t].append(i)
    caused = defaultdict(int)
    for i in np.flatnonzero(truck_late.to_numpy()):
        for t in delayed[i][1]:
            d, _ = net.deliver(o.at[i, 'ready'], o.at[i, 'site'], o.at[i, 'station'], with_overrides(delay, {t: 0.0}))
            caused[t] += d <= o.at[i, 'promise']

    def saved(truck, new_delay):
        return sum(1 for i in on_truck[truck] if truck_late.iat[i]
                   and net.deliver(o.at[i, 'ready'], o.at[i, 'site'], o.at[i, 'station'],
                                   with_overrides(delay, {truck: new_delay}))[0] <= o.at[i, 'promise'])

    rec, trucks = net.c['recovery'], []
    for t, n in caused.items():
        if n == 0:
            continue
        options = dict(swap=dict(cost=rec['swap_cost'], saved=saved(t, max(0.0, delay(t) - rec['swap_recovers_hours']))),
                       split=dict(cost=max(rec['split_minimum_cost'], rec['split_cost_per_km'] * net.km(*t[0])), saved=saved(t, 0.0)))
        pick = cheapest(options)
        trucks.append(dict(plan=name, lane=f'{t[0][0]}>{t[0][1]}', departure=t[1], delay_hours=round(delay(t), 2),
                           parcels_on_board=len(on_truck[t]), late_parcels_caused=n, best_option=pick,
                           cost=options[pick]['cost'] if pick else 0.0, parcels_saved=options[pick]['saved'] if pick else 0,
                           new_delay=(max(0.0, delay(t) - rec['swap_recovers_hours']) if pick == 'swap' else 0.0)))
    overrides = {((r['lane'].split('>')[0], r['lane'].split('>')[1]), r['departure']): r['new_delay'] for r in trucks if r['best_option']}
    recovered = [net.deliver(r, s, t, with_overrides(delay, overrides))[0] > p
                 for r, s, t, p in zip(o['ready'], o['site'], o['station'], o['promise'])]
    summary = dict(plan=name, labor_cost=round(labor, 2), on_time_unit_share_in_warehouse=round(on_time_units, 4),
                   orders=len(orders), unfinished_orders=unfinished,
                   late_without_truck_delays=int(o['late_without_truck_delays'].sum()),
                   late_with_truck_delays=int(o['late_with_truck_delays'].sum()),
                   late_caused_by_trucks=int(truck_late.sum()),
                   late_caused_by_weather=int((o['late_with_truck_delays'] & ~pd.Series(late_if_calm)).sum()),
                   at_risk_trucks=len(trucks),
                   late_after_truck_recovery=int(sum(recovered)),
                   truck_recovery_cost=round(sum(r['cost'] for r in trucks if r['best_option']), 2))
    return summary, pd.DataFrame(trucks), o


def main():
    net = Network()
    orders = load_orders()
    shares = site_shares()
    stations = {k: v['population_millions'] for k, v in CONFIG['stations'].items()}
    orders['site'] = [weighted_pick(c, shares, 'site') for c in orders['customer']]
    orders['station'] = [weighted_pick(c, stations, 'station') for c in orders['customer']]
    OUT.mkdir(exist_ok=True)
    rows, all_trucks, daily = [], [], []
    for name, plan in CONFIG['staffing_plans'].items():
        summary, trucks, detail = evaluate_plan(name, plan, orders, net)
        rows.append(summary)
        all_trucks.append(trucks)
        weather_late = detail['late_with_truck_delays'] & ~detail['late_if_calm']
        daily.append(detail.assign(weather_late=weather_late).groupby('promise').agg(
            parcels=('order_id', 'size'), late=('late_with_truck_delays', 'sum'), late_from_weather=('weather_late', 'sum'))
            .reset_index().rename(columns={'promise': 'promise_date'}).assign(plan=name))
        print(json.dumps(summary), flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / 'plan_comparison.csv', index=False)
    trucks = pd.concat(all_trucks)
    if len(trucks):
        trucks.drop(columns=['new_delay']).sort_values(['plan', 'late_parcels_caused'], ascending=[True, False]).to_csv(
            OUT / 'at_risk_trucks.csv', index=False)
    pd.concat(daily)[['plan', 'promise_date', 'parcels', 'late', 'late_from_weather']].to_csv(OUT / 'daily_late.csv', index=False)
    routes = orders.groupby(['site', 'station']).agg(orders=('order_id', 'size'), units=('units', 'sum')).reset_index()
    routes['km'] = [round(net.km(a, b)) for a, b in zip(routes['site'], routes['station'])]
    routes['promise_transit_days'] = [1 if k <= CONFIG['promise']['next_day_within_km'] else 2 for k in routes['km']]
    routes.to_csv(OUT / 'routes.csv', index=False)
    lanes_file = REPO / 'data/raw/ors/truck_lanes.json'  # from last_mile/fetch_road_matrix.py
    if lanes_file.exists():  # the assumed lane drive times next to OpenRouteService truck routes (no traffic)
        road = json.loads(lanes_file.read_text())
        i = {p: n for n, p in enumerate(road['places'])}
        lanes = sorted({(s, sc) for s in CONFIG['sites'] for sc in CONFIG['sort_centers']}
                       | {(v['sort_center'], k) for k, v in CONFIG['stations'].items()})
        pd.DataFrame([dict(lane=f'{a}>{b}', straight_km=round(net.km(a, b)), road_km=round(road['km'][i[a]][i[b]]),
                           straight_line_drive_hours=round(net.km(a, b) / CONFIG['truck_speed_kmh'], 2),
                           road_truck_hours=round(road['minutes'][i[a]][i[b]] / 60, 2)) for a, b in lanes]
                     ).to_csv(OUT / 'road_check.csv', index=False)
    (OUT / 'summary.json').write_text(json.dumps(dict(evidence_status=CONFIG['evidence_status'], plans=rows), indent=2, default=str) + '\n')
    pd.set_option('display.width', 220)
    print(table.T.to_string())


if __name__ == '__main__':
    main()
