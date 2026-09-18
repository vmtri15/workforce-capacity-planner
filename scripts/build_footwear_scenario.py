"""Build an isolated, uncalibrated footwear demand/absence experiment."""

import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.backlog import simulate_backlog


def main():
    source = ROOT / 'data/raw/warehouse_picking/Customer_Order.csv'
    units = Counter()
    records = Counter()
    zero_quantity_rows = 0
    with source.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle, delimiter=';'):
            day = datetime.strptime(row['creationDate'], '%d/%m/%Y %H:%M').date()
            quantity = int(row['quantity (units)'])
            if quantity < 0:
                raise ValueError('Negative order quantity requires review')
            zero_quantity_rows += quantity == 0
            units[day] += quantity
            records[day] += 1
    start, end = min(units), max(units)
    # Deliberately assumed single-site policy, unrelated to source operator IDs.
    policy = dict(workers=6, paid_hours=8, productive_factor=0.85,
                  units_per_productive_hour=40, operating_weekdays=[0, 1, 2, 3, 4],
                  initial_backlog=0, recovery_calendar_days=14)
    peak = max((day for day in units if day.weekday() < 5), key=units.get)
    absence_dates = []
    day = peak
    while len(absence_dates) < 5:
        if day.weekday() < 5:
            absence_dates.append(day.isoformat())
        day += timedelta(days=1)
    scenarios = []
    for name, absences in [('no_absences', {}),
                           ('synthetic_peak_absences', {day: 2 for day in absence_dates})]:
        daily = []
        day = start
        while day <= end + timedelta(days=policy['recovery_calendar_days']):
            operating = day.weekday() in policy['operating_weekdays']
            absent = absences.get(day.isoformat(), 0)
            present = policy['workers'] - absent if operating else 0
            capacity = math.floor(present * policy['paid_hours'] *
                                  policy['productive_factor'] * policy['units_per_productive_hour'])
            daily.append(dict(date=day.isoformat(), arrivals=units[day], capacity=capacity,
                              source_rows=records[day], source_record_present=day in records,
                              recovery_day=day > end, scheduled_workers=policy['workers'] if operating else 0,
                              synthetic_absent_workers=absent, present_workers=present))
            day += timedelta(days=1)
        results = simulate_backlog(daily)
        scenarios.append(dict(name=name, daily=results, summary=dict(
            arrivals=sum(r['arrivals'] for r in results),
            completed=sum(r['completed'] for r in results),
            ending_backlog=results[-1]['closing_backlog'],
            peak_backlog=max(r['closing_backlog'] for r in results),
            backlog_unit_days=sum(r['closing_backlog'] for r in results),
            max_backlog_age_days=max(r['oldest_backlog_days'] for r in results))))
    output = dict(evidence_status='assumed_uncalibrated_diagnostic_only',
                  source_file=str(source.relative_to(ROOT)),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  source_start=str(start), source_end=str(end), source_rows=sum(records.values()),
                  zero_quantity_rows=zero_quantity_rows,
                  source_dates=len(records), policy=policy, synthetic_absence_dates=absence_dates,
                  caveats=[
                      'Order creation date is an arrival proxy, not execution time.',
                      'All source rows retained; duplicates are not silently removed.',
                      'Missing source dates and recovery days assume zero arrivals.',
                      'All arrivals are available before daily processing; intraday timing is ignored.',
                      'Capacity, weekdays and absences are assumptions, not measured workforce behavior.',
                      'Two fictional workers absent for five weekdays starting at the busiest weekday: retrospective stress test, not forecast.',
                      'No joins to picking completions, Kaggle employees, OpenPack or JTH.',
                      'Daily FIFO permits partial orders; no packing or shipping completion is modeled.'
                  ], scenarios=scenarios)
    target = ROOT / 'data/processed/footwear_backlog_scenario.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + '\n')
    for scenario in scenarios:
        print(scenario['name'], json.dumps(scenario['summary']))


if __name__ == '__main__':
    main()
