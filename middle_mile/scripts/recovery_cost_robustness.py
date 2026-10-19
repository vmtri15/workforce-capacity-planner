"""Does the recovery recommendation survive other cost assumptions?

The recovery costs in config/recovery.json are hypothetical. This re-runs the policy comparison from
evaluate_recovery.py (main departure schedule) with the swap cost, the split load cost and the hours
a trailer swap recovers changed, and checks whether "use the cheapest option on each at risk truck"
still has the lowest cost per parcel saved and still saves almost every parcel that would slip.

Scenarios:
  cost grid   swap cost x 0.5, 1, 2, 4 against split cost x 0.5, 1, 2, 4 (swap recovers the base hours)
  swap power  the hours a swap recovers set to 1, 2, 3 and 5 (base costs)
Savings do not depend on cost, so a full re-simulation only runs when the chosen options change.

Run from the project root, after evaluate_recovery.py:
    python3 scripts/recovery_cost_robustness.py
"""
import copy
import itertools
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from build_journeys import load_config
from evaluate_recovery import Overlay, cheapest, option_costs, option_overrides, policy_result, saved
from simulate_disruptions import Network, evaluate, lane_variability, load_parcels, make_delays, summarize

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed'
COST_MULTIPLIERS = [0.5, 1, 2, 4]
SWAP_HOURS = [1, 2, 3, 5]


def variant(recovery, swap_mult, split_mult, hours):
    r = copy.deepcopy(recovery)
    r['swap_trailer'].update(cost=recovery['swap_trailer']['cost'] * swap_mult, recovers_hours=hours)
    r['split_load'].update(
        extra_truck_cost_per_km=recovery['split_load']['extra_truck_cost_per_km'] * split_mult,
        extra_truck_minimum_cost=recovery['split_load']['extra_truck_minimum_cost'] * split_mult)
    return r


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
    net = Network(config, delays_config['departure_sensitivity']['main'])
    delay = make_delays(delays_config, scales, start, end, net)
    rows = evaluate(parcels, net, delay=delay)
    base = summarize(rows, len(parcels))
    on_truck = defaultdict(list)
    for i, (_, _, used, _) in enumerate(rows):
        for truck in used:
            on_truck[truck].append(i)
    at_risk = [t for t, idx in on_truck.items() if any(rows[i][0] > 0 for i in idx)]
    late = [t for t in on_truck if delay.get(t, 0.0) >= recovery['untargeted_swap_delay_threshold_hours']]
    swap_saved, split_saved, policy_cache = {}, {}, {}
    for truck in at_risk:
        split_saved[truck] = saved(parcels, rows, on_truck[truck], net, Overlay(delay, {truck: 0.0}))[0]
    at_risk = [t for t in at_risk if split_saved[t] > 0]  # trucks where splitting the load saves a parcel

    def swap_saved_for(truck, hours):
        if (truck, hours) not in swap_saved:
            ov = option_overrides(truck, delay, {'recovers_hours': hours})['swap']
            swap_saved[truck, hours] = saved(parcels, rows, on_truck[truck], net, Overlay(delay, ov))[0]
        return swap_saved[truck, hours]

    def rerun(key, overrides, cost):
        if key not in policy_cache:
            policy_cache[key] = policy_result(parcels, net, delay, overrides, 0.0, base)
        r = dict(policy_cache[key], cost=round(cost, 2))
        r['cost_per_parcel_saved'] = round(cost / r['parcels_saved'], 2) if r['parcels_saved'] > 0 else None
        return r

    print('slipped', base['parcels_slipped'], '| at risk trucks', len(at_risk), '| late trucks', len(late), flush=True)
    scenarios = [(a, b, recovery['swap_trailer']['recovers_hours']) for a, b in itertools.product(COST_MULTIPLIERS, repeat=2)]
    scenarios += [(1, 1, h) for h in SWAP_HOURS if h != recovery['swap_trailer']['recovers_hours']]
    out = []
    for swap_mult, split_mult, hours in scenarios:
        v = variant(recovery, swap_mult, split_mult, hours)
        choice, cost3, costs2 = {}, 0.0, 0.0
        for truck in at_risk:
            c = option_costs(truck, config, v)
            costs2 += c['split']
            options = dict(swap=dict(cost=c['swap'], saved=swap_saved_for(truck, hours)),
                           split=dict(cost=c['split'], saved=split_saved[truck]))
            pick = cheapest(options)
            if pick:
                choice[truck] = pick
                cost3 += options[pick]['cost']
        ov3 = {}
        for truck, pick in choice.items():
            ov3.update(option_overrides(truck, delay, v['swap_trailer'])[pick])
        results = {
            'swap_every_late_truck': rerun(('swap_all', hours), {t: option_overrides(t, delay, v['swap_trailer'])['swap'][t] for t in late},
                                           v['swap_trailer']['cost'] * len(late)),
            'split_at_risk_trucks': rerun('split_all', {t: 0.0 for t in at_risk}, costs2),
            'cheapest_option': rerun(('cheapest', frozenset(choice.items()), hours), ov3, cost3)}
        winner = min((k for k in results if results[k]['cost_per_parcel_saved'] is not None),
                     key=lambda k: results[k]['cost_per_parcel_saved'])
        row = dict(swap_cost_multiplier=swap_mult, split_cost_multiplier=split_mult, swap_recovers_hours=hours,
                   lowest_cost_per_parcel_saved=winner,
                   cheapest_share_of_events_using_swap=round(sum(p == 'swap' for p in choice.values()) / max(len(choice), 1), 3),
                   cheapest_share_of_slips_saved=round(results['cheapest_option']['parcels_saved'] / base['parcels_slipped'], 4))
        for name, r in results.items():
            row[f'{name}_cost'] = r['cost']
            row[f'{name}_parcels_saved'] = r['parcels_saved']
            row[f'{name}_cost_per_parcel_saved'] = r['cost_per_parcel_saved']
        out.append(row)
        print(swap_mult, split_mult, hours, winner, row['cheapest_option_cost_per_parcel_saved'], row['cheapest_share_of_slips_saved'], flush=True)
    table = pd.DataFrame(out)
    table.to_csv(OUT / 'recovery_cost_robustness.csv', index=False)
    wins = int((table['lowest_cost_per_parcel_saved'] == 'cheapest_option').sum())
    summary = dict(scenarios=len(table), cheapest_option_has_lowest_cost_per_parcel_saved=wins,
                   cheapest_option_cost_per_parcel_saved_range=[float(table['cheapest_option_cost_per_parcel_saved'].min()),
                                                                float(table['cheapest_option_cost_per_parcel_saved'].max())],
                   cheapest_option_share_of_slips_saved_min=float(table['cheapest_share_of_slips_saved'].min()),
                   scenarios_where_something_else_wins=table.loc[table['lowest_cost_per_parcel_saved'] != 'cheapest_option',
                                                                 ['swap_cost_multiplier', 'split_cost_multiplier', 'swap_recovers_hours',
                                                                  'lowest_cost_per_parcel_saved']].to_dict('records'))
    (OUT / 'recovery_cost_robustness.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
