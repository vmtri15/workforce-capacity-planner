"""Truck delays, cancellations and hub closures on the simulated journeys: how many parcels slip, and how
many of those become new breaches of the real promised delivery date.

Real: the parcels, their handover times and real slack (promised date minus actual delivery date).
Assumed: the network, the schedule and the delay model, set in config/network.json and config/delays.json.

A parcel that misses the destination cutoff because of a disruption slips by whole days. Its real delivery
date moves by the same number of days. It is a new breach when its real slack was zero or more and is
smaller than the slip. Parcels that were already late in reality are counted separately.

Scenarios:
  routine       every scheduled truck departure gets a random arrival delay
  cancellation  each lane day is cancelled with a small probability
  closure       one hub is closed for one whole day, tried for every hub and every day of the data
Each truck's own impact in the routine run is its marginal effect: the slip and breaches that disappear
when only that truck's delay is removed. The routine run is repeated for other departure times to show
how much the lane results depend on the assumed schedule.

Run from the project root, after build_journeys.py:
    python3 scripts/simulate_disruptions.py
"""
import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from build_journeys import HOUR, lane_hours, load_config, next_departure, state_to_hub, wave_date

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed'
MINUTE = pd.Timedelta(minutes=1)


class Network:
    """The assumed network with the lane travel times worked out once."""

    def __init__(self, config, departures=None):
        self.config = config
        self.departures = departures or config['departures']
        self.sort = config['sort_hours'] * HOUR
        self.cutoff_hour = config['cutoff_hour']
        self.main = config['main_hub']
        self.hours = {}

    def lane_time(self, lane):
        if lane not in self.hours:
            self.hours[lane] = lane_hours(self.config, *lane)[0] * HOUR
        return self.hours[lane]

    def lanes_for(self, origin, destination, n_legs):
        return [(origin, destination)] if n_legs == 1 else [(origin, self.main), (self.main, destination)]


def reopen(closed, hub, t):
    """The first moment at or after `t` when the hub is open, given the closed days of each hub."""
    days = closed.get(hub) if closed else None
    while days and t.date() in days:
        t = t.normalize() + pd.Timedelta(days=1)
    return t


def run_parcel(handover, lanes, net, delay=None, cancelled=None, closed=None):
    """Arrival time at the destination hub and the trucks (lane, departure) the parcel actually used."""
    t = reopen(closed, lanes[0][0], handover)
    used = []
    for lane in lanes:
        ready = t + net.sort
        while True:
            dep = next_departure(ready, net.departures)
            if (cancelled and (lane, dep.date()) in cancelled) or (closed and reopen(closed, lane[0], dep) != dep):
                ready = dep + MINUTE
                continue
            break
        used.append((lane, dep))
        t = dep + net.lane_time(lane) + (delay.get((lane, dep), 0.0) if delay else 0.0) * HOUR
        t = reopen(closed, lane[1], t)
    return t, used


def slip_days(arrival, base_arrival, cutoff_hour):
    return (wave_date(arrival, cutoff_hour) - wave_date(base_arrival, cutoff_hour)).days


def breach_kind(slack, slip):
    """'new' if the slip breaks a promise that was kept, 'worse' if the parcel was already late."""
    if slip <= 0:
        return None
    return 'new' if 0 <= slack < slip else ('worse' if slack < 0 else None)


def lane_variability(parcels, config):
    """Real 90th percentile over median transit days for the parcels on each lane, scaled to mean 1."""
    hub = state_to_hub(config)
    p = parcels.assign(o=parcels['seller_state'].map(hub), d=parcels['customer_state'].map(hub))
    g = p.groupby(['o', 'd'])['transit_days'].agg(lambda x: x.quantile(0.9) / x.median())
    return g / g.mean()


def make_delays(delays_config, scales, start, end, net):
    """A random delay for every scheduled departure on every lane between `start` and `end`."""
    rng = np.random.default_rng(delays_config['seed'])
    r = delays_config['routine']
    out = {}
    for lane in sorted(scales):
        day = start.normalize()
        while day <= end:
            for clock in net.departures:
                hour, minute = map(int, clock.split(':'))
                dep = day + pd.Timedelta(hours=hour, minutes=minute)
                scale = scales[lane] if r['scale_by_real_lane_variability'] else 1.0
                out[lane, dep] = r['median_delay_hours'] * scale * float(np.exp(r['sigma'] * rng.standard_normal()))
            day += pd.Timedelta(days=1)
    return out


def evaluate(parcels, net, **disruption):
    """Per parcel slip and breach kind under the disruption."""
    rows = []
    for p in parcels:
        base, _ = run_parcel(p['handover'], p['lanes'], net)
        arrival, used = run_parcel(p['handover'], p['lanes'], net, **disruption)
        slip = slip_days(arrival, base, net.cutoff_hour)
        rows.append((slip, breach_kind(p['slack'], slip), used, base))
    return rows


def summarize(rows, n_parcels):
    slips = np.array([r[0] for r in rows])
    kinds = [r[1] for r in rows]
    return dict(parcels=n_parcels, parcels_slipped=int((slips > 0).sum()),
                share_slipped=round(float((slips > 0).mean()), 5),
                mean_slip_days_when_slipped=round(float(slips[slips > 0].mean()), 3) if (slips > 0).any() else 0.0,
                new_breaches=kinds.count('new'), share_new_breaches=round(kinds.count('new') / n_parcels, 5),
                already_late_made_later=kinds.count('worse'))


class WithoutDelay:
    """The delay table with one truck's delay removed, without copying the table."""

    def __init__(self, delay, truck):
        self.delay, self.truck = delay, truck

    def get(self, key, default=0.0):
        return 0.0 if key == self.truck else self.delay.get(key, default)


def truck_impact(parcels, rows, net, delay):
    """Marginal impact of each truck: slip and new breaches that disappear when its own delay is removed."""
    impact = defaultdict(lambda: dict(parcels_on_board=0, slipped_parcels=0, slip_days_caused=0, new_breaches_caused=0))
    for p, (slip, kind, used, base) in zip(parcels, rows):
        for truck in used:
            impact[truck]['parcels_on_board'] += 1
        if slip <= 0:
            continue
        for truck in used:
            arrival, _ = run_parcel(p['handover'], p['lanes'], net, delay=WithoutDelay(delay, truck))
            slip_without = slip_days(arrival, base, net.cutoff_hour)
            kind_without = breach_kind(p['slack'], slip_without)
            caused = slip - slip_without
            if caused > 0:
                impact[truck]['slipped_parcels'] += 1
                impact[truck]['slip_days_caused'] += caused
            impact[truck]['new_breaches_caused'] += int(kind == 'new' and kind_without != 'new')
    table = pd.DataFrame([dict(lane=f'{lane[0]}>{lane[1]}', departure=dep, delay_hours=round(delay.get((lane, dep), 0.0), 2), **v)
                          for (lane, dep), v in impact.items()])
    return table


def load_parcels(config):
    journeys = pd.read_csv(OUT / 'journeys.csv', parse_dates=['handover_ts'])
    net = Network(config)
    return [dict(handover=h, lanes=net.lanes_for(o, d, n), slack=s)
            for h, o, d, n, s in zip(journeys['handover_ts'], journeys['origin_hub'], journeys['dest_hub'],
                                      journeys['n_legs'], journeys['slack_days'])]


def main():
    config = load_config()
    delays_config = json.loads((ROOT / 'config/delays.json').read_text())
    parcels = load_parcels(config)
    all_parcels = pd.read_csv(OUT / 'parcels.csv', usecols=['seller_state', 'customer_state', 'transit_days'])
    scales = lane_variability(all_parcels, config)
    lanes = sorted({lane for p in parcels for lane in p['lanes']})
    scales = {lane: float(scales.get(lane, 1.0)) for lane in lanes}
    start = min(p['handover'] for p in parcels).normalize() - pd.Timedelta(days=1)
    end = max(p['handover'] for p in parcels).normalize() + pd.Timedelta(days=8)
    summary = dict(evidence_status=delays_config['evidence_status'], parcels_with_truck_leg=len(parcels))
    pd.DataFrame([dict(lane=f'{a}>{b}', variability_scale=round(v, 3)) for (a, b), v in scales.items()]
                 ).to_csv(OUT / 'lane_variability.csv', index=False)

    # routine delays, with each truck's own impact, and the departure time sensitivity
    sensitivity = {}
    for name, departures in delays_config['departure_sensitivity'].items():
        net = Network(config, departures)
        delay = make_delays(delays_config, scales, start, end, net)
        rows = evaluate(parcels, net, delay=delay)
        sensitivity[name] = dict(departures=departures, **summarize(rows, len(parcels)))
        print(name, sensitivity[name], flush=True)
        if name == 'main':
            summary['routine'] = sensitivity[name]
            table = truck_impact(parcels, rows, net, delay)
            table = table[(table['slipped_parcels'] > 0) | (table['new_breaches_caused'] > 0)]
            table.sort_values(['new_breaches_caused', 'slip_days_caused'], ascending=False
                              ).to_csv(OUT / 'truck_impact_routine.csv', index=False)
            lane_view = table.groupby('lane')[['slipped_parcels', 'slip_days_caused', 'new_breaches_caused']].sum()
            summary['routine_by_lane'] = lane_view.sort_values('new_breaches_caused', ascending=False).to_dict('index')
    summary['departure_sensitivity'] = sensitivity

    # random lane day cancellations
    net = Network(config)
    rng = np.random.default_rng(delays_config['seed'] + 1)
    days = pd.date_range(start, end, freq='D')
    p_cancel = delays_config['cancellation']['lane_day_probability']
    cancelled = {(lane, d.date()) for lane in lanes for d in days if rng.random() < p_cancel}
    rows = evaluate(parcels, net, cancelled=cancelled)
    summary['cancellation'] = dict(cancelled_lane_days=len(cancelled), **summarize(rows, len(parcels)))
    print('cancellation', summary['cancellation'], flush=True)

    # one hub closed for one whole day, for every hub and every day of the data
    by_day = defaultdict(list)
    for p in parcels:
        by_day[p['handover'].date()].append(p)
    hubs = list(config['hubs'])
    results = []
    first, last = min(by_day), max(by_day)
    day = first
    while day <= last:
        window = [p for k in range(-4, 1) for p in by_day.get(day + timedelta(days=k), [])]
        for hub in hubs:
            touched = [p for p in window if any(hub in lane for lane in p['lanes'])]
            if not touched:
                continue
            rows = evaluate(touched, net, closed={hub: {day}})
            kinds = [r[1] for r in rows]
            results.append(dict(hub=hub, day=day, parcels_slipped=sum(r[0] > 0 for r in rows),
                                new_breaches=kinds.count('new'), already_late_made_later=kinds.count('worse')))
        day += timedelta(days=1)
    closure = pd.DataFrame(results)
    hub_table = closure.groupby('hub').agg(
        days_simulated=('day', 'size'), mean_parcels_slipped=('parcels_slipped', 'mean'),
        p95_parcels_slipped=('parcels_slipped', lambda x: x.quantile(0.95)), worst_day_parcels_slipped=('parcels_slipped', 'max'),
        mean_new_breaches=('new_breaches', 'mean'), worst_day_new_breaches=('new_breaches', 'max')).reset_index()
    hub_table.sort_values('mean_new_breaches', ascending=False).round(2).to_csv(OUT / 'hub_closure_summary.csv', index=False)
    summary['hub_closure'] = hub_table.sort_values('mean_new_breaches', ascending=False).round(2).to_dict('records')
    (OUT / 'disruption_summary.json').write_text(json.dumps(summary, indent=2, default=str) + '\n')
    pd.set_option('display.width', 200)
    print(hub_table.sort_values('mean_new_breaches', ascending=False).round(2).to_string(index=False))


if __name__ == '__main__':
    main()
