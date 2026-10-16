"""Put every real Olist parcel on a simulated truck journey through an assumed hub network.

Real: the parcels, their handover times, seller and customer states, and each parcel's slack (promised
date minus actual delivery date). Assumed: the hubs, trucks, departures, sort time, truck speed and the
destination cutoff, all set in config/network.json.

Each parcel reaches its origin hub at its real handover time, is sorted, and waits for the next truck.
Parcels between two spokes go through the main hub. At the destination hub, arriving before the cutoff
means the next morning delivery wave, otherwise the wave one day later. This is the schedule with no
delays; delays and recovery are added in later steps.

Outputs (data/processed/):
  journeys.csv        one row per parcel that uses a truck (not committed, rebuild with this script)
  legs.csv            one row per parcel and truck leg (not committed)
  trucks.csv          one row per truck departure (not committed)
  lane_summary.csv    one row per lane
  journey_summary.json  headline numbers

Run from the project root, after prep_parcels.py:
    python3 scripts/build_journeys.py
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from prep_parcels import haversine_km

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed'
HOUR = pd.Timedelta(hours=1)
DAY = pd.Timedelta(days=1)


def load_config():
    return json.loads((ROOT / 'config/network.json').read_text())


def state_to_hub(config):
    mapping = {}
    for hub, info in config['hubs'].items():
        for state in info['states']:
            if state in mapping:
                raise ValueError(f'{state} is assigned to two hubs')
            mapping[state] = hub
    return mapping


def lane_hours(config, origin, destination):
    a, b = config['hubs'][origin], config['hubs'][destination]
    km = float(haversine_km(a['lat'], a['lng'], b['lat'], b['lng']))
    return config['loading_hours'] + km / config['truck_speed_kmh'], km


def next_departure(ready, departures):
    """The first scheduled departure at or after `ready`."""
    day = ready.normalize()
    for offset in (0, 1):
        for clock in departures:
            hour, minute = map(int, clock.split(':'))
            candidate = day + pd.Timedelta(days=offset, hours=hour, minutes=minute)
            if candidate >= ready:
                return candidate
    raise ValueError('no departure found')


def wave_date(arrival, cutoff_hour):
    """Next morning wave if the truck arrives by the cutoff, otherwise one day later."""
    cutoff = arrival.normalize() + pd.Timedelta(hours=cutoff_hour)
    return (arrival.normalize() + DAY * (1 if arrival <= cutoff else 2)).date()


def schedule_leg(ready, lanes, config, capacity=None):
    """Departure and arrival for each parcel on one leg, first come first served by ready time.

    With `capacity` (parcels per truck by lane) a full truck sends the parcel on the next departure.
    """
    order = np.argsort(ready.to_numpy(), kind='stable')
    departure = np.empty(len(ready), dtype='datetime64[ns]')
    loads = {}
    for i in order:
        lane = lanes[i]
        dep = next_departure(ready.iloc[i], config['departures'])
        if capacity is not None:
            while loads.get((lane, dep), 0) >= capacity[lane]:
                dep = next_departure(dep + pd.Timedelta(minutes=1), config['departures'])
            loads[lane, dep] = loads.get((lane, dep), 0) + 1
        departure[i] = dep.to_datetime64()
    departure = pd.Series(pd.to_datetime(departure), index=ready.index)
    hours = pd.Series([lane_hours(config, *lane)[0] for lane in lanes], index=ready.index)
    return departure, departure + hours * HOUR


def lane_capacity(departure, lanes, config):
    """1.3 times the busiest day's volume on the lane, divided by the number of departures."""
    frame = pd.DataFrame({'lane': lanes, 'day': departure.dt.date})
    busiest = frame.groupby(['lane', 'day']).size().groupby('lane').max()
    return {lane: math.ceil(config['capacity_factor'] * n / len(config['departures']))
            for lane, n in busiest.items()}


def build(parcels, config):
    """Return journeys, legs and trucks for the parcels that need at least one truck leg."""
    hub = state_to_hub(config)
    main = config['main_hub']
    p = parcels.copy()
    p['origin_hub'] = p['seller_state'].map(hub)
    p['dest_hub'] = p['customer_state'].map(hub)
    if p[['origin_hub', 'dest_hub']].isna().any().any():
        raise ValueError('a state is not assigned to a hub')
    p = p[p['origin_hub'] != p['dest_hub']].copy()  # same hub parcels have no truck leg
    through_main = (p['origin_hub'] != main) & (p['dest_hub'] != main)
    p['leg1_to'] = np.where(through_main, main, p['dest_hub'])
    lanes1 = list(zip(p['origin_hub'], p['leg1_to']))
    ready1 = p['handover_ts'] + config['sort_hours'] * HOUR

    # first pass without capacity gives the busiest day per lane, which sets truck capacity
    dep1, arr1 = schedule_leg(ready1, lanes1, config)
    leg2 = p[through_main]
    lanes2 = list(zip([main] * len(leg2), leg2['dest_hub']))
    dep2, _ = schedule_leg(arr1[through_main] + config['sort_hours'] * HOUR, lanes2, config)
    caps = {**lane_capacity(dep2, lanes2, config), **lane_capacity(dep1, lanes1, config)}
    caps = {lane: max(caps.get(lane, 1), 1) for lane in set(lanes1) | set(lanes2)}
    unconstrained_dep1 = dep1

    dep1, arr1 = schedule_leg(ready1, lanes1, config, caps)
    p['leg1_departure'], p['leg1_arrival'] = dep1, arr1
    p['leg1_delay_h'] = (dep1 - unconstrained_dep1) / HOUR  # waited because the truck was full
    final = arr1.copy()
    p['leg2_departure'] = pd.NaT
    p['leg2_arrival'] = pd.NaT
    if len(leg2):
        d2, a2 = schedule_leg(arr1[through_main] + config['sort_hours'] * HOUR, lanes2, config, caps)
        p.loc[through_main, 'leg2_departure'] = d2
        p.loc[through_main, 'leg2_arrival'] = a2
        final.loc[through_main] = a2
    p['n_legs'] = np.where(through_main, 2, 1)
    p['arrival_at_destination_hub'] = final
    cutoff = final.dt.normalize() + pd.Timedelta(hours=config['cutoff_hour'])
    p['cutoff_margin_h'] = (cutoff - final) / HOUR  # negative means the truck arrives after the cutoff
    p['wave_date'] = [wave_date(t, config['cutoff_hour']) for t in final]
    p['slack_days'] = (p['promised_ts'] - p['delivered_ts']) / DAY  # real: negative means already late

    rows = []
    for leg, (frm, to, dep, arr) in enumerate([('origin_hub', 'leg1_to', 'leg1_departure', 'leg1_arrival'),
                                                ('leg2_from', 'dest_hub', 'leg2_departure', 'leg2_arrival')], 1):
        d = p if leg == 1 else p[through_main].assign(leg2_from=main)
        rows.append(pd.DataFrame({'order_id': d['order_id'], 'leg': leg, 'from_hub': d[frm], 'to_hub': d[to],
                                  'departure': d[dep], 'arrival': d[arr]}))
    legs = pd.concat(rows, ignore_index=True)
    legs['truck_id'] = (legs['from_hub'] + '>' + legs['to_hub'] + '@' + legs['departure'].dt.strftime('%Y%m%d%H%M'))
    trucks = legs.groupby('truck_id').agg(from_hub=('from_hub', 'first'), to_hub=('to_hub', 'first'),
                                           departure=('departure', 'first'), arrival=('arrival', 'first'),
                                           parcels=('order_id', 'size')).reset_index()
    trucks['capacity'] = [caps[(a, b)] for a, b in zip(trucks['from_hub'], trucks['to_hub'])]
    trucks['utilization'] = trucks['parcels'] / trucks['capacity']
    journeys = p[['order_id', 'seller_state', 'customer_state', 'origin_hub', 'dest_hub', 'n_legs', 'handover_ts',
                  'leg1_delay_h', 'arrival_at_destination_hub', 'cutoff_margin_h', 'wave_date', 'promised_ts',
                  'delivered_ts', 'slack_days', 'weight_g']]
    return journeys, legs, trucks, caps


def main():
    config = load_config()
    parcels = pd.read_csv(OUT / 'parcels.csv', parse_dates=['handover_ts', 'delivered_ts', 'promised_ts'])
    journeys, legs, trucks, caps = build(parcels, config)
    lanes = trucks.groupby(['from_hub', 'to_hub']).agg(
        trucks=('truck_id', 'size'), parcels=('parcels', 'sum'), mean_utilization=('utilization', 'mean'),
        p95_utilization=('utilization', lambda x: x.quantile(0.95)), capacity=('capacity', 'first')).reset_index()
    lanes['distance_km'] = [round(lane_hours(config, a, b)[1]) for a, b in zip(lanes['from_hub'], lanes['to_hub'])]
    journeys.to_csv(OUT / 'journeys.csv', index=False)
    legs.to_csv(OUT / 'legs.csv', index=False)
    trucks.to_csv(OUT / 'trucks.csv', index=False)
    lanes.sort_values('parcels', ascending=False).to_csv(OUT / 'lane_summary.csv', index=False)

    makes = journeys['cutoff_margin_h'] >= 0
    margin = journeys.loc[makes, 'cutoff_margin_h']
    summary = dict(
        evidence_status=config['evidence_status'],
        parcels_total=len(parcels), parcels_with_truck_leg=len(journeys),
        share_with_truck_leg=round(len(journeys) / len(parcels), 4),
        parcels_through_main_hub=int((journeys['n_legs'] == 2).sum()),
        lanes=len(lanes), truck_departures=len(trucks),
        mean_truck_utilization=round(float(trucks['utilization'].mean()), 3),
        parcels_that_waited_for_a_full_truck=int((journeys['leg1_delay_h'] > 0).sum()),
        share_arriving_after_cutoff=round(float((~makes).mean()), 4),
        share_of_cutoff_makers_with_margin_under_1h=round(float((margin < 1).mean()), 4),
        share_of_cutoff_makers_with_margin_under_3h=round(float((margin < 3).mean()), 4),
        share_with_real_slack_under_1_day=round(float((journeys['slack_days'] < 1).mean()), 4),
        share_already_late_in_reality=round(float((journeys['slack_days'] < 0).mean()), 4))
    (OUT / 'journey_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    pd.set_option('display.width', 200)
    print(json.dumps(summary, indent=2))
    print(lanes.sort_values('parcels', ascending=False).round(2).to_string(index=False))


if __name__ == '__main__':
    main()
