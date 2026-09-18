"""Run the predeclared staffing grid on both duplicate interpretations."""
import csv
import hashlib
import itertools
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.service_scenarios import simulate
from analyze_operational_actions import read_csv, segment_orders, write_csv


def main():
    config_path = ROOT / 'config/footwear_scenarios.json'
    config = json.loads(config_path.read_text())
    source = ROOT / 'data/raw/warehouse_picking/Customer_Order.csv'
    raw = read_csv(source, ';')
    unique = list({tuple(r.items()): r for r in raw}.values())
    output = ROOT / 'data/processed/service_scenarios'
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with (output / 'daily.csv').open('w', newline='') as handle:
        writer = None
        for basis, records in [('retained', raw), ('deduplicated_sensitivity', unique)]:
            demand = Counter()
            for order in segment_orders(records):
                demand[date.fromisoformat(order['date'])] += order['units']
            grid = itertools.product(config['scheduled_workers'], config['absent_workers_each_operating_day'],
                                     config['units_per_productive_hour'], config['service_operating_days'])
            for workers, absent, rate, window in grid:
                summary, rows = simulate(demand, workers, absent, rate, window, config)
                case = f'{basis}_w{workers}_a{absent}_r{rate}_d{window}'
                results.append(dict(case=case, basis=basis, **summary))
                for row in rows:
                    item = dict(case=case, **row)
                    if writer is None:
                        writer = csv.DictWriter(handle, fieldnames=list(item))
                        writer.writeheader()
                    writer.writerow(item)
    write_csv(output / 'comparison.csv', results)
    thresholds = []
    for basis, absent, rate, window in itertools.product(
            ['retained', 'deduplicated_sensitivity'], config['absent_workers_each_operating_day'],
            config['units_per_productive_hour'], config['service_operating_days']):
        selected = [r for r in results if r['basis']==basis and r['absent']==absent
                    and r['rate']==rate and r['service_days']==window and r['target_met'] is True]
        thresholds.append(dict(basis=basis, absent=absent, rate=rate, service_days=window,
                               minimum_tested_workers=min(r['workers'] for r in selected) if selected else None,
                               interpretation='Lowest passing value in tested 4-12 grid; not an actual hiring recommendation'))
    write_csv(output / 'staffing_thresholds.csv', thresholds)
    manifest = dict(config=config, cases=len(results), sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [config_path,source]},
                    deadline_definition='Arrival operating day counts as day 1; closed-day arrivals start next operating day; due at day end.',
                    metric='Unit-weighted service, not whole-order or shipping SLA; arrivals available at day start.',
                    limits=['Absences persist every operating day, representing a stress level, not measured attendance.',
                            'Missing dates assume zero demand; initial backlog zero; no packing, costs or shift feasibility constraints.',
                            'Historical replay, not forecast or calibrated staffing. No overtime or temporary workers in this grid.',
                            '4 is the lower search bound; a result of 4 does not prove fewer workers would fail.'])
    (output / 'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(cases=len(results), retained_no_absence=[r for r in thresholds if r['basis']=='retained' and r['absent']==0]),indent=2))


if __name__ == '__main__':
    main()
