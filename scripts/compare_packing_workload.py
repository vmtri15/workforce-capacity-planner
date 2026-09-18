"""Diagnostic only. Explicit coefficients; does not alter optimizer inputs."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.packing import packing_hours


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixed-seconds', type=float, required=True)
    parser.add_argument('--seconds-per-unit', type=float, required=True)
    args = parser.parse_args()
    data = json.loads((ROOT/'data/processed/outbound_audit.json').read_text())
    totals = data['planning_window']['totals']
    scale = 5
    comparisons = []
    for ratio in (1, 2, 4):
        packages = totals['candidate_outbound_orders'] * scale * ratio
        units = totals['candidate_units'] * scale
        comparisons.append({'assumed_packages_per_order': ratio,
            'estimated_packages': packages, 'modeled_units': units,
            'productive_hours': packing_hours(packages, units, args.fixed_seconds, args.seconds_per_unit)})
    result = {'status': 'diagnostic_only_uncalibrated_not_optimizer_input',
        'source_sha256': data['source_sha256'], 'demand_scale': scale,
        'fixed_seconds_per_package': args.fixed_seconds, 'seconds_per_unit': args.seconds_per_unit,
        'legacy_50_jobs_per_hour': totals['legacy_invoice_count']*scale/50,
        'candidate_orders_only_50_jobs_per_hour': totals['candidate_outbound_orders']*scale/50,
        'package_count_is_assumed': True, 'allowances_included': False,
        'comparisons': comparisons}
    (ROOT/'data/processed/packing_workload_diagnostic.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
