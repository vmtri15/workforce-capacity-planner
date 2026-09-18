"""Evidence-first analyses; no changes to baseline planning or dashboard data."""
import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.backlog import simulate_backlog


def read_csv(path, delimiter=','):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path, rows):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def size_key(value):
    return format(Decimal(value).normalize(), 'f') if value.strip() else 'MISSING'


def packing_seconds(items, fixed, per_item):
    if type(items) is not int or not 1 <= items <= 5:
        raise ValueError('Experimental reference only supports integer item counts 1-5')
    return fixed + per_item * items


def segment_orders(rows):
    orders = {}
    for r in rows:
        key = r['orderNumber']
        day = datetime.strptime(r['creationDate'], '%d/%m/%Y %H:%M').date()
        if key not in orders:
            orders[key] = dict(date=day, customer=r['codCustomer'].strip(), units=0, source_rows=0)
        if orders[key]['date'] != day or orders[key]['customer'] != r['codCustomer'].strip():
            raise ValueError('Order ID spans dates/customers; review aggregation key')
        q = int(r['quantity (units)'])
        if q < 0:
            raise ValueError('Negative demand requires review')
        orders[key]['units'] += q
        orders[key]['source_rows'] += 1
    return [dict(order_id=k, date=str(v['date']), month=str(v['date'])[:7],
                 units=v['units'], source_rows=v['source_rows'],
                 segment='zero' if v['units'] == 0 else 'small_1_5' if v['units'] <= 5 else 'large_over_5')
            for k, v in sorted(orders.items())]


def monthly_summary(orders, basis):
    result = []
    for month in sorted({r['month'] for r in orders}):
        selected = [r for r in orders if r['month'] == month]
        daily = Counter()
        for r in selected:
            daily[r['date']] += r['units']
        total = sum(daily.values())
        large = [r for r in selected if r['segment'] == 'large_over_5']
        result.append(dict(basis=basis, month=month, recorded_dates=len(daily),
                           orders=len(selected), units=total,
                           large_order_share=len(large)/len(selected),
                           large_unit_share=sum(r['units'] for r in large)/total,
                           daily_mean=statistics.mean(daily.values()),
                           daily_p90=sorted(daily.values())[math.ceil(.9*len(daily))-1],
                           daily_max=max(daily.values())))
    return result


def response_case(demand, rate, policy):
    start, end = min(demand), max(demand)
    day = start
    closing = 0
    daily = []
    base_capacity = int(Decimal(48) * Decimal('.85') * Decimal(rate))
    while day <= end + timedelta(days=14):
        operating = day.weekday() < 5
        arrivals = demand.get(day, 0)
        capacity = base_capacity if operating else 0
        extra_paid_hours = 0
        # Temps are requested from the previous calendar day's closing queue.
        if operating and policy == 'temporary' and closing > base_capacity:
            extra_paid_hours = 16
            capacity += int(Decimal(16) * Decimal('.85') * Decimal(rate) * Decimal('.8'))
        if operating and policy == 'overtime' and closing + arrivals > capacity:
            extra_paid_hours = 12
            capacity += int(Decimal(12) * Decimal('.85') * Decimal(rate))
        daily.append(dict(date=str(day), arrivals=arrivals, capacity=capacity,
                          extra_paid_hours=extra_paid_hours))
        closing = max(0, closing + arrivals - capacity)
        day += timedelta(days=1)
    result = simulate_backlog(daily)
    return dict(rate=rate, policy=policy, arrivals=sum(demand.values()),
                peak_backlog=max(r['closing_backlog'] for r in result),
                backlog_unit_days=sum(r['closing_backlog'] for r in result),
                max_backlog_age_days=max(r['oldest_backlog_days'] for r in result),
                ending_backlog=result[-1]['closing_backlog'],
                extra_paid_hours=sum(r['extra_paid_hours'] for r in result)), result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--locations', type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / 'data/raw/warehouse_picking/Customer_Order.csv'
    picks_path = ROOT / 'data/raw/warehouse_picking/Picking_Wave.csv'
    packing_path = ROOT / 'data/processed/openpack_timing_evaluation.json'
    out = ROOT / 'data/processed/operational_actions'
    out.mkdir(parents=True, exist_ok=True)
    raw = read_csv(source, ';')
    seen = set()
    unique = []
    duplicates = []
    for number, row in enumerate(raw, 2):
        key = tuple(row.values())
        if key in seen:
            duplicates.append(dict(source_line=number, order_id=row['orderNumber'],
                                   units=int(row['quantity (units)']), wave=row['waveNumber']))
        else:
            seen.add(key)
            unique.append(row)
    monthly = []
    policies = []
    policy_days = []
    totals = {}
    for basis, rows in [('retained', raw), ('deduplicated_sensitivity', unique)]:
        orders = segment_orders(rows)
        write_csv(out / f'orders_{basis}.csv', orders)
        monthly.extend(monthly_summary(orders, basis))
        totals[basis] = dict(rows=len(rows), units=sum(r['units'] for r in orders), orders=len(orders))
        demand = Counter()
        for r in orders:
            demand[datetime.fromisoformat(r['date']).date()] += r['units']
        for rate in (30, 40, 50):
            for policy in ('carryover', 'overtime', 'temporary'):
                summary, daily = response_case(demand, rate, policy)
                policies.append(dict(basis=basis, **summary))
                policy_days.extend(dict(basis=basis, rate=rate, policy=policy, **r) for r in daily)
    write_csv(out / 'monthly_segments.csv', monthly)
    write_csv(out / 'response_comparison.csv', policies)
    write_csv(out / 'response_daily.csv', policy_days)
    write_csv(out / 'duplicate_rows_for_review.csv', duplicates)

    locations = {r['originalLocation'].strip(): r for r in read_csv(args.locations)}
    picks = read_csv(picks_path, ';')
    pick_units = Counter()
    pick_locations = defaultdict(Counter)
    unmatched = Counter()
    for r in picks:
        key = (r['reference'], size_key(r['Size (US)']))
        q = int(r['quantityToPick (units)'])
        location = r['locations'].strip()
        pick_units[key] += q
        pick_locations[key][location] += q
        if location not in locations:
            unmatched[location] += q
    sku_units = Counter()
    sku_unique = Counter()
    reference_months = defaultdict(Counter)
    for rows, counter in [(raw, sku_units), (unique, sku_unique)]:
        for r in rows:
            counter[(r['Reference'], size_key(r['Size (US)']))] += int(r['quantity (units)'])
    for r in raw:
        month = datetime.strptime(r['creationDate'], '%d/%m/%Y %H:%M').strftime('%Y-%m')
        reference_months[month][r['Reference']] += int(r['quantity (units)'])
    top_months = Counter(ref for c in reference_months.values() for ref, _ in c.most_common(10))
    shortlist = []
    for rank, (key, q) in enumerate(sku_units.most_common(30), 1):
        locs = pick_locations[key]
        shortlist.append(dict(rank=rank, reference=key[0], size=key[1], order_units=q,
                              deduplicated_order_units=sku_unique[key], pick_file_units=pick_units[key],
                              reference_months_in_top10=top_months[key[0]],
                              distinct_pick_locations=len(locs),
                              unknown_location_units=sum(n for loc, n in locs.items() if loc not in locations),
                              locations=';'.join(f'{loc}:{n}' for loc, n in locs.most_common()),
                              action='Review access and replenishment; no measured travel-time savings'))
    write_csv(out / 'slotting_review_shortlist.csv', shortlist)
    write_csv(out / 'unmatched_locations.csv', [dict(location=k, pick_units=v) for k,v in unmatched.most_common()])
    write_csv(out / 'monthly_top_references.csv', [dict(month=m, rank=i, reference=k, units=v,
              month_unit_share=v/sum(c.values())) for m,c in sorted(reference_months.items())
              for i,(k,v) in enumerate(c.most_common(10),1)])

    evaluation = json.loads(packing_path.read_text())
    packing = evaluation['scenarios']['S1']
    fixed = packing['exploratory_fit']['fixed_seconds']
    slope = packing['exploratory_fit']['seconds_per_item']
    write_csv(out / 'experimental_packing_reference.csv', [dict(items=n,
              fitted_station_seconds=packing_seconds(n,fixed,slope),
              constant_station_seconds=packing['eligible']['mean_seconds'],
              observed_median_seconds=packing['by_item_count'][str(n)]['median_seconds'],
              sample_boxes=packing['by_item_count'][str(n)]['boxes']) for n in range(1,6)])
    audit = dict(totals=totals, exact_duplicate_extra_rows=len(duplicates),
                 duplicate_extra_units=sum(r['units'] for r in duplicates),
                 zero_quantity_rows=sum(int(r['quantity (units)'])==0 for r in raw),
                 missing_size_rows=sum(not r['Size (US)'].strip() for r in raw),
                 pick_units=sum(pick_units.values()), unmatched_location_codes=len(unmatched),
                 unmatched_location_units=sum(unmatched.values()),
                 duplicate_resolution='Unresolved: no unique source row ID or extraction contract; retain raw, show sensitivity.',
                 location_scope='Independent pick-file location counts, not matched customer-order completions.',
                 packing_scope='Experimental 1-5 item station reference only; not applied to footwear or paid staffing.',
                 policy_assumptions=dict(workers=6, paid_hours=8, productive_factor=.85,
                     rates=[30,40,50], operating_days='Monday-Friday', initial_backlog=0,
                     arrivals='Creation-date proxy; available at day start; missing dates zero',
                     overtime='All six workers receive two paid extra hours when start-of-day work exceeds base capacity',
                     temporary='Two eight-hour shifts at 80% productivity if previous calendar-day backlog exceeds base capacity; assumed next-day availability',
                     recovery='14 calendar days of zero new demand; no costs, deadlines, legal or fatigue constraints modeled'),
                 source_fingerprints={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in [source,picks_path,args.locations,packing_path]})
    (out / 'audit_and_assumptions.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(dict(audit=audit,monthly=monthly,policies=policies),indent=2))


if __name__ == '__main__':
    main()
