"""Six Sigma checks on the planner's own data: an I-MR chart and Cpk for packing time, and a p-chart of daily late parcels.

Packing time: real OpenPack lab recordings (one-item boxes in scenario S1, the same screen as evaluate_openpack_timing.py),
in recording order, against the 90 seconds per unit the planner's 40 units per hour base case allows (upper limit only).
Late parcels: the middle-mile replay's daily counts (middle_mile/connected/results/daily_late.csv), grouped by promise date.

Run after build_connected.py, before build_static_dashboard.py:
    .venv/bin/python scripts/build_process_control.py
"""
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TIMING = ROOT / 'data/processed/openpack_timing_audit.csv'
DAILY = ROOT / 'middle_mile/connected/results/daily_late.csv'
OUTPUT = ROOT / 'data/processed/process_control.json'
COSTS = json.loads((ROOT / 'config/staffing_cost_scenarios.json').read_text())
BASE_RATE = 40  # units per productive hour, the planner's base case
D2, D4 = 1.128, 3.267  # control chart constants for moving ranges of 2


def imr(values):
    """Individuals and moving range chart limits, with the points beyond 3 sigma."""
    x = np.asarray(values, float)
    mr = np.abs(np.diff(x))
    center, mr_bar = x.mean(), mr.mean()
    sigma = mr_bar / D2
    ucl, lcl = center + 3 * sigma, center - 3 * sigma
    return dict(center=center, sigma_within=sigma, ucl=ucl, lcl=lcl, mr_bar=mr_bar, mr_ucl=D4 * mr_bar,
                beyond_limits=[int(i) for i in np.flatnonzero((x > ucl) | (x < lcl))])


def cpk_upper(mean, sigma, usl):
    """One-sided capability: how many 3 sigma widths fit between the mean and the upper limit."""
    return (usl - mean) / (3 * sigma)


def p_chart(late, parcels):
    """Overall late share and each day's 3 sigma limits; flags days above the upper limit."""
    late, n = np.asarray(late, float), np.asarray(parcels, float)
    p = late.sum() / n.sum()
    se = np.sqrt(p * (1 - p) / n)
    ucl, lcl = p + 3 * se, np.maximum(0, p - 3 * se)
    return dict(p_bar=p, ucl=ucl, lcl=lcl, above=late / n > ucl)


def packing():
    with TIMING.open() as f:
        rows = [r for r in csv.DictReader(f) if r['screen_pass'] == 'True' and abs(float(r['gap_seconds'])) <= .001
                and r['scenario'] == 'S1' and r['item_count'] == '1']
    rows.sort(key=lambda r: (r['recording_id'], r['session'], int(r['box'])))
    x = [float(r['station_seconds_excluding_picking']) for r in rows]
    chart, usl = imr(x), 3600 / BASE_RATE
    overall = float(np.std(x, ddof=1))
    people = sorted({r['person_id'] for r in rows})
    return dict(
        source='OpenPack packing recordings, scenario S1, one-item boxes, packing station time excluding picking',
        boxes=len(x), people=len(people), usl_seconds=usl, usl_basis=f'{BASE_RATE} units per productive hour (planner base case)',
        mean_seconds=round(chart['center'], 2), sigma_within=round(chart['sigma_within'], 2), sigma_overall=round(overall, 2),
        ucl=round(chart['ucl'], 2), lcl=round(chart['lcl'], 2), mr_bar=round(chart['mr_bar'], 2), mr_ucl=round(chart['mr_ucl'], 2),
        points_beyond_limits=len(chart['beyond_limits']),
        cpk=round(cpk_upper(chart['center'], chart['sigma_within'], usl), 2),
        ppk=round(cpk_upper(chart['center'], overall, usl), 2),
        share_over_usl=round(float(np.mean(np.array(x) > usl)), 4),
        cpk_at_stress_rates={str(rate): float(round(cpk_upper(chart['center'], chart['sigma_within'], 3600 / rate), 2))
                             for rate in COSTS['stress_productivity_rates']},
        ppk_at_stress_rates={str(rate): float(round(cpk_upper(chart['center'], overall, 3600 / rate), 2))
                             for rate in COSTS['stress_productivity_rates']},
        seconds_for_cpk_1_33=round(chart['center'] + 4 * chart['sigma_within'], 1),
        seconds_for_ppk_1_33=round(chart['center'] + 4 * overall, 1),  # Ppk is the fair number while the process is out of control
        person_means={p: round(float(np.mean([v for v, r in zip(x, rows) if r['person_id'] == p])), 1) for p in people},
        points=[dict(seconds=round(v, 2), person=r['person_id']) for v, r in zip(x, rows)])


def late_parcels():
    with DAILY.open() as f:
        rows = list(csv.DictReader(f))
    plans = {}
    for plan in dict.fromkeys(r['plan'] for r in rows):
        days = [r for r in rows if r['plan'] == plan]
        late, n = [int(r['late']) for r in days], [int(r['parcels']) for r in days]
        chart = p_chart(late, n)
        above = [d for d, flag in zip(days, chart['above']) if flag]
        busy = 1.5 * float(np.median(n))  # a peak day: half again the usual daily volume
        plans[plan] = dict(
            days=len(days), parcels=sum(n), late=sum(late), p_bar=round(chart['p_bar'], 5),
            days_above_limit=len(above), late_on_those_days=sum(int(d['late']) for d in above),
            weather_late_on_those_days=sum(int(d['late_from_weather']) for d in above),
            peak_day_parcels=busy, late_on_those_days_that_were_peaks=sum(int(d['late']) for d in above if int(d['parcels']) >= busy),
            points=[dict(date=d['promise_date'], parcels=int(d['parcels']), late=int(d['late']), ucl=round(u, 4), above=bool(a))
                    for d, u, a in zip(days, chart['ucl'], chart['above'])])
    return plans


def main():
    result = dict(packing=packing(), late_parcels=late_parcels())
    OUTPUT.write_text(json.dumps(result, indent=1) + '\n')
    pk, six = result['packing'], result['late_parcels']['affordable_6_workers']
    print(f"Packing: {pk['boxes']} boxes, mean {pk['mean_seconds']} s, Cpk {pk['cpk']} at {pk['usl_seconds']:.0f} s, "
          f"{pk['share_over_usl']:.1%} over; Cpk by rate {pk['cpk_at_stress_rates']}")
    print(f"6 workers: {six['days_above_limit']} of {six['days']} days above the p-chart limit hold "
          f"{six['late_on_those_days']} of {six['late']} late parcels")


if __name__ == '__main__':
    main()
