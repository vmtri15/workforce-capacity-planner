"""Build a 2023 site-level capacity replay without changing the legacy database."""
from __future__ import annotations

import csv
import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMAND = ROOT / 'tableau/data/demand_daily.csv'
DATABASE = ROOT / 'data/workforce_planner.db'
OUTPUT = ROOT / 'data/processed/network_capacity_2023.json'

PICK_RATES = {'low': 30.0, 'base': 40.0, 'high': 50.0}
PACK_RATES = {'low': 35.0, 'base': 50.0, 'high': 65.0}


def nearest_rank(values, percentile):
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def allocate_integer(total, shares):
    raw = [(site['site_id'], total * site['allocation_share']) for site in shares]
    result = {site_id: math.floor(value) for site_id, value in raw}
    ranked = sorted(raw, key=lambda item: (-(item[1] - math.floor(item[1])), item[0]))
    for site_id, _ in ranked[:total - sum(result.values())]:
        result[site_id] += 1
    return result


def load_daily_demand():
    daily = defaultdict(lambda: {'orders': 0, 'units': 0})
    with DEMAND.open(newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            if row['basis'] != 'retained':
                continue
            daily[row['date']]['orders'] += int(row['orders'])
            daily[row['date']]['units'] += int(row['units'])
    return [{'date': day, **values} for day, values in sorted(daily.items())]


def load_reference_data():
    connection = sqlite3.connect(DATABASE)
    try:
        connection.row_factory = sqlite3.Row
        sites = [dict(row) for row in connection.execute(
            'SELECT site_id, site_name, allocation_share, allocation_basis FROM sites ORDER BY site_id')]
        wages = {(row['benchmark_area'], row['role_id']): row['median_hourly_wage'] for row in connection.execute(
            'SELECT benchmark_area, role_id, median_hourly_wage FROM wage_benchmarks')}
        assumptions = {row['assumption_key']: row['numeric_value'] for row in connection.execute(
            'SELECT assumption_key, numeric_value FROM scenario_assumptions WHERE numeric_value IS NOT NULL')}
        return sites, wages, assumptions
    finally:
        connection.close()


def wage_area(site_id):
    return 'Kenosha, WI' if site_id == 'kenosha' else 'Chicago-Naperville-Elgin, IL-IN'


def build():
    daily = load_daily_demand()
    sites, wages, assumptions = load_reference_data()
    paid_hours = float(assumptions['paid_hours_per_shift'])
    productive_factor = float(assumptions['productive_time_factor'])
    productive_hours = paid_hours * productive_factor
    service_target = float(assumptions['service_target'])
    shifts = int(assumptions['shifts_per_day'])
    unit_p95 = nearest_rank([row['units'] for row in daily], .95)
    order_p95 = nearest_rank([row['orders'] for row in daily], .95)

    staffing = []
    for site in sites:
        share = site['allocation_share']
        plan = {
            'fulfillment_associate': math.ceil(unit_p95 * share / (PICK_RATES['base'] * productive_hours)),
            'packing_associate': max(shifts, math.ceil(order_p95 * share / (PACK_RATES['base'] * productive_hours))),
            'warehouse_supervisor': shifts,
            'shipping_receiving_coordinator': 1,
        }
        for role, headcount in plan.items():
            staffing.append({
                'site_id': site['site_id'], 'site_name': site['site_name'], 'role_id': role,
                'scheduled_headcount': headcount, 'paid_hours_per_person': paid_hours,
                'median_hourly_wage': wages[(wage_area(site['site_id']), role)],
                'evidence': 'Modeled staffing using 2023 observed demand and documented assumptions',
            })

    cases = []
    for case in PICK_RATES:
        site_summary = {site['site_id']: {
            'site_id': site['site_id'], 'site_name': site['site_name'], 'required_hours': 0.0,
            'gap_hours': 0.0, 'role_days': 0, 'target_met_role_days': 0,
        } for site in sites}
        chart = []
        site_chart = []
        for record in daily:
            orders = allocate_integer(record['orders'], sites)
            units = allocate_integer(record['units'], sites)
            day_required = 0.0
            day_available = 0.0
            for site in sites:
                site_required = 0.0
                site_available = 0.0
                for role, quantity, rate in (
                    ('fulfillment_associate', units[site['site_id']], PICK_RATES[case]),
                    ('packing_associate', orders[site['site_id']], PACK_RATES[case]),
                ):
                    headcount = next(row['scheduled_headcount'] for row in staffing
                                     if row['site_id'] == site['site_id'] and row['role_id'] == role)
                    required = quantity / rate
                    available = headcount * productive_hours
                    coverage = 1.0 if quantity == 0 else min(1.0, available / required)
                    summary = site_summary[site['site_id']]
                    summary['required_hours'] += required
                    summary['gap_hours'] += max(required - available, 0.0)
                    summary['role_days'] += 1
                    summary['target_met_role_days'] += int(coverage >= service_target)
                    day_required += required
                    day_available += available
                    site_required += required
                    site_available += available
                site_chart.append({
                    'date': record['date'], 'site_id': site['site_id'],
                    'required_hours': round(site_required, 4),
                    'available_hours': round(site_available, 4),
                    'gap_hours': round(max(site_required - site_available, 0.0), 4),
                })
            chart.append({'date': record['date'], 'required_hours': round(day_required, 4),
                          'available_hours': round(day_available, 4)})

        daily_wage_cost = sum(row['scheduled_headcount'] * row['paid_hours_per_person'] * row['median_hourly_wage']
                              for row in staffing)
        summaries = []
        for summary in site_summary.values():
            site_staff = [row for row in staffing if row['site_id'] == summary['site_id']]
            summary['scheduled_headcount'] = sum(row['scheduled_headcount'] for row in site_staff)
            summary['recorded_period_wage_cost'] = round(sum(
                row['scheduled_headcount'] * row['paid_hours_per_person'] * row['median_hourly_wage']
                for row in site_staff) * len(daily), 2)
            summary['target_met_share'] = round(summary.pop('target_met_role_days') / summary.pop('role_days'), 6)
            summary['required_hours'] = round(summary['required_hours'], 4)
            summary['gap_hours'] = round(summary['gap_hours'], 4)
            summaries.append(summary)
        cases.append({
            'productivity_case': case, 'pick_rate_units_per_hour': PICK_RATES[case],
            'pack_rate_orders_per_hour': PACK_RATES[case], 'daily': chart,
            'site_daily': site_chart,
            'site_summary': summaries,
            'network_summary': {
                'required_hours': round(sum(row['required_hours'] for row in chart), 4),
                'gap_hours': round(sum(row['gap_hours'] for row in summaries), 4),
                'scheduled_headcount': sum(row['scheduled_headcount'] for row in staffing),
                'recorded_period_wage_cost': round(daily_wage_cost * len(daily), 2),
            },
        })

    assert round(sum(site['allocation_share'] for site in sites), 8) == 1
    assert all(sum(allocate_integer(row['units'], sites).values()) == row['units'] for row in daily)
    assert cases[0]['network_summary']['gap_hours'] >= cases[1]['network_summary']['gap_hours'] >= cases[2]['network_summary']['gap_hours']
    return {
        'metadata': {
            'title': '2023 observed-demand network capacity replay',
            'source_window_start': daily[0]['date'], 'source_window_end': daily[-1]['date'],
            'recorded_dates': len(daily), 'observed_units': sum(row['units'] for row in daily),
            'observed_orders': sum(row['orders'] for row in daily),
            'missing_date_treatment': 'Excluded; missing source dates are not assumed to be zero demand',
            'site_allocation': 'Modeled using rounded 2025 Q4 QCEW NAICS 493 employment shares',
            'staffing_basis': 'Fixed staffing sized at the 95th percentile of recorded daily 2023 workload using base productivity',
            'created_at': datetime.now(timezone.utc).isoformat(),
        },
        'sites': sites, 'staffing': staffing, 'cases': cases,
        'quality_checks': ['site shares sum to 1', 'daily unit allocation preserves totals',
                           'capacity gaps decline as productivity increases'],
    }


if __name__ == '__main__':
    result = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {OUTPUT.relative_to(ROOT)} for {result["metadata"]["recorded_dates"]} recorded dates.')
