"""Recovery options for late trucks: do nothing, swap in a faster trailer, or split the load.

For routine truck delays (see simulate_disruptions.py) every truck that causes parcels to slip is a
recovery event. Each option is tested by re-running the parcels on that truck. Four policies are then
applied to the whole network and compared on parcels saved from slipping, new breaches avoided and cost:
  do_nothing            no recovery
  swap_every_late_truck swap the trailer on every truck delayed by at least the threshold
  split_at_risk_trucks  split the load on every truck whose delay would make parcels slip
  cheapest_option       on each at risk truck use whichever of swap or split costs less per parcel saved
The comparison is repeated for the three departure schedules in config/delays.json, so the recommendation
does not depend on one assumed schedule. All costs are the hypothetical units in config/recovery.json.

Run from the project root, after simulate_disruptions.py:
    python3 scripts/evaluate_recovery.py
"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from build_journeys import lane_hours, load_config
from simulate_disruptions import (Network, breach_kind, evaluate, lane_variability, load_parcels, make_delays,
                                  run_parcel, slip_days, summarize)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed'


class Overlay:
    """The delay table with some trucks' delays replaced, without copying the table."""

    def __init__(self, delay, overrides):
        self.delay, self.overrides = delay, overrides

    def get(self, key, default=0.0):
        return self.overrides[key] if key in self.overrides else self.delay.get(key, default)


def option_overrides(truck, delay, swap):
    """Delay overrides for the two recovery options on one truck."""
    return {'swap': {truck: max(0.0, delay.get(truck, 0.0) - swap['recovers_hours'])}, 'split': {truck: 0.0}}


def option_costs(truck, config, recovery):
    km = lane_hours(config, *truck[0])[1]
    split = max(recovery['split_load']['extra_truck_minimum_cost'], recovery['split_load']['extra_truck_cost_per_km'] * km)
    return {'swap': recovery['swap_trailer']['cost'], 'split': split}


def saved(parcels, rows, indices, net, delay):
    """Parcels no longer slipping and new breaches avoided for the parcels on one truck."""
    parcels_saved = breaches_avoided = 0
    for i in indices:
        slip, kind, _, base = rows[i]
        new_arrival, _ = run_parcel(parcels[i]['handover'], parcels[i]['lanes'], net, delay=delay)
        new_slip = slip_days(new_arrival, base, net.cutoff_hour)
        parcels_saved += int(slip > 0 and new_slip == 0)
        breaches_avoided += int(kind == 'new' and breach_kind(parcels[i]['slack'], new_slip) != 'new')
    return parcels_saved, breaches_avoided


def cheapest(options):
    """The option with the lowest cost per parcel saved among those that save at least one parcel."""
    useful = {name: o for name, o in options.items() if o['saved'] > 0}
    if not useful:
        return None
    return min(useful, key=lambda name: (useful[name]['cost'] / useful[name]['saved'], useful[name]['cost']))


def policy_result(parcels, net, delay, overrides, cost, base):
    rows = evaluate(parcels, net, delay=Overlay(delay, overrides))
    s = summarize(rows, len(parcels))
    saved_parcels = base['parcels_slipped'] - s['parcels_slipped']
    return dict(cost=round(cost, 2), parcels_slipped=s['parcels_slipped'], parcels_saved=saved_parcels,
                new_breaches=s['new_breaches'], new_breaches_avoided=base['new_breaches'] - s['new_breaches'],
                cost_per_parcel_saved=round(cost / saved_parcels, 2) if saved_parcels > 0 else None)


def run_schedule(name, departures, parcels, config, delays_config, recovery, scales, start, end):
    net = Network(config, departures)
    delay = make_delays(delays_config, scales, start, end, net)
    rows = evaluate(parcels, net, delay=delay)
    base = summarize(rows, len(parcels))
    on_truck = defaultdict(list)
    for i, (slip, _, used, _) in enumerate(rows):
        for truck in used:
            on_truck[truck].append(i)

    events = []
    for truck, indices in on_truck.items():
        if not any(rows[i][0] > 0 for i in indices):
            continue
        ov = option_overrides(truck, delay, recovery['swap_trailer'])
        costs = option_costs(truck, config, recovery)
        options = {}
        for opt in ('swap', 'split'):
            s, b = saved(parcels, rows, indices, net, Overlay(delay, ov[opt]))
            options[opt] = dict(cost=costs[opt], saved=s, breaches_avoided=b)
        choice = cheapest(options)
        events.append(dict(schedule=name, lane=f'{truck[0][0]}>{truck[0][1]}', departure=truck[1],
                           delay_hours=round(delay.get(truck, 0.0), 2), parcels_on_board=len(indices),
                           parcels_at_risk=sum(rows[i][0] > 0 for i in indices),
                           swap_cost=options['swap']['cost'], swap_parcels_saved=options['swap']['saved'],
                           split_cost=options['split']['cost'], split_parcels_saved=options['split']['saved'],
                           split_breaches_avoided=options['split']['breaches_avoided'],
                           best_option=choice, truck_key=truck, ov=ov, options=options))

    threshold = recovery['untargeted_swap_delay_threshold_hours']
    late = [t for t in on_truck if delay.get(t, 0.0) >= threshold]
    swap_all = {t: option_overrides(t, delay, recovery['swap_trailer'])['swap'][t] for t in late}
    at_risk = [e for e in events if e['options']['split']['saved'] > 0]
    results = {
        'do_nothing': policy_result(parcels, net, delay, {}, 0.0, base),
        'swap_every_late_truck': policy_result(parcels, net, delay, {t: v for t, v in swap_all.items()},
                                               recovery['swap_trailer']['cost'] * len(late), base),
        'split_at_risk_trucks': policy_result(
            parcels, net, delay, {e['truck_key']: 0.0 for e in at_risk}, sum(e['options']['split']['cost'] for e in at_risk), base),
    }
    chosen = [e for e in events if e['best_option']]
    overrides = {}
    for e in chosen:
        overrides.update(e['ov'][e['best_option']])
    results['cheapest_option'] = policy_result(parcels, net, delay, overrides,
                                               sum(e['options'][e['best_option']]['cost'] for e in chosen), base)
    for e in events:
        for k in ('truck_key', 'ov', 'options'):
            e.pop(k)
    return base, results, pd.DataFrame(events), len(late)


def main():
    config = load_config()
    delays_config = json.loads((ROOT / 'config/delays.json').read_text())
    recovery = json.loads((ROOT / 'config/recovery.json').read_text())
    parcels = load_parcels(config)
    all_parcels = pd.read_csv(OUT / 'parcels.csv', usecols=['seller_state', 'customer_state', 'transit_days'])
    scales = lane_variability(all_parcels, config)
    lanes = sorted({lane for p in parcels for lane in p['lanes']})
    scales = {lane: float(scales.get(lane, 1.0)) for lane in lanes}
    start = min(p['handover'] for p in parcels).normalize() - pd.Timedelta(days=1)
    end = max(p['handover'] for p in parcels).normalize() + pd.Timedelta(days=8)

    rows, summary = [], dict(evidence_status=recovery['evidence_status'], currency=recovery['currency'], schedules={})
    for name, departures in delays_config['departure_sensitivity'].items():
        base, results, events, n_late = run_schedule(name, departures, parcels, config, delays_config, recovery,
                                                     scales, start, end)
        for policy, r in results.items():
            rows.append(dict(schedule=name, policy=policy, **r))
        summary['schedules'][name] = dict(departures=departures, baseline=base, trucks_delayed_over_threshold=n_late,
                                          at_risk_trucks=len(events), policies=results)
        if name == 'main':
            events['best_cost_per_parcel_saved'] = [
                (e.swap_cost / e.swap_parcels_saved if e.best_option == 'swap' else e.split_cost / e.split_parcels_saved)
                if e.best_option else np.nan for e in events.itertuples()]
            ranked = events.dropna(subset=['best_cost_per_parcel_saved']).sort_values('best_cost_per_parcel_saved')
            ranked['cost'] = np.where(ranked['best_option'] == 'swap', ranked['swap_cost'], ranked['split_cost'])
            ranked['saved'] = np.where(ranked['best_option'] == 'swap', ranked['swap_parcels_saved'], ranked['split_parcels_saved'])
            ranked['cumulative_cost'] = ranked['cost'].cumsum()
            ranked['cumulative_parcels_saved'] = ranked['saved'].cumsum()
            ranked.drop(columns=['schedule']).to_csv(OUT / 'recovery_events_main.csv', index=False)
        print(name, json.dumps(results), flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / 'recovery_policies.csv', index=False)
    best = table[table['policy'] != 'do_nothing'].dropna(subset=['cost_per_parcel_saved']
                ).sort_values('cost_per_parcel_saved').groupby('schedule').first()['policy']
    summary['lowest_cost_per_parcel_saved_by_schedule'] = best.to_dict()
    (OUT / 'recovery_summary.json').write_text(json.dumps(summary, indent=2, default=str) + '\n')
    pd.set_option('display.width', 200)
    print(table.to_string(index=False))
    print(best.to_dict())


if __name__ == '__main__':
    main()
