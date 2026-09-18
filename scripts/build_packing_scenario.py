"""Build calendar-complete packing-hour sensitivities without changing the database."""
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.packing import estimated_packing_jobs, packing_hours


def main():
    config = json.loads((ROOT/'config/packing_scenario.json').read_text())
    start, end = config['source_window_start'], config['source_window_end']
    with (ROOT/'data/processed/reviewed_order_mix.csv').open() as f:
        mix = [r for r in csv.DictReader(f) if start <= r['source_date'] <= end]
    scale = config['demand_scale']
    output = []
    for size in config['units_per_job_sensitivity']:
        day = date.fromisoformat(start)
        while day <= date.fromisoformat(end):
            selected = [r for r in mix if r['source_date'] == day.isoformat()]
            orders = sum(int(r['orders']) for r in selected) * scale
            units = sum(float(r['units'])*int(r['orders']) for r in selected) * scale
            jobs = sum(estimated_packing_jobs(float(r['units']), size)*int(r['orders']) for r in selected) * scale
            hours = packing_hours(jobs, units, config['fixed_seconds_per_job'], config['seconds_per_unit'])
            output.append(dict(source_date=day.isoformat(), assumed_units_per_job=size,
                modeled_orders=orders, modeled_units=units, estimated_jobs=jobs,
                productive_packing_hours=hours))
            day += timedelta(days=1)
    audit = json.loads((ROOT/'data/processed/reviewed_outbound_audit.json').read_text())
    totals = audit['planning_window']['totals']
    summaries = []
    for size in config['units_per_job_sensitivity']:
        group = [r for r in output if r['assumed_units_per_job'] == size]
        assert len(group) == 56
        assert sum(r['modeled_orders'] for r in group) == totals['candidate_outbound_orders']*scale
        assert sum(r['modeled_units'] for r in group) == totals['candidate_units']*scale
        summaries.append(dict(assumed_units_per_job=size,
            estimated_jobs=sum(r['estimated_jobs'] for r in group),
            productive_hours=sum(r['productive_packing_hours'] for r in group)))
    assert all(a['productive_hours'] >= b['productive_hours'] for a,b in zip(summaries, summaries[1:]))
    with (ROOT/'data/processed/packing_scenario_daily.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0])); writer.writeheader(); writer.writerows(output)
    result = dict(config=config, source_sha256=audit['source_sha256'], summaries=summaries,
        checks='PASS: 56-day calendars, candidate-order and unit reconciliation, sensitivity ordering')
    (ROOT/'data/processed/packing_scenario_results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
