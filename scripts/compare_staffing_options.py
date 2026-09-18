"""Phase 3A: bounded single-option comparisons, not roster optimization."""
import json
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compare(connection):
    connection.row_factory = sqlite3.Row
    results = []
    for case in ('low', 'base', 'high'):
        rows = connection.execute('''
            SELECT c.*, s.median_hourly_wage
            FROM daily_capacity_results c JOIN staffing_plans s
            USING (run_id, site_id, role_id)
            JOIN planning_runs p USING (run_id)
            WHERE p.productivity_case = ?
        ''', (case,)).fetchall()
        if len(rows) != 336:
            raise ValueError('Run the planning engine first; expected 336 rows per case')
        for target in (0.95, 1.0):
            for option in ('no_action', 'overtime', 'temporary_shifts', 'extra_daily_positions'):
                # Explicit prototype controls; neither vendor quotes nor measured availability.
                factor, ot_multiplier, ot_daily_limit = 0.85, 1.5, 2.0
                temp_multiplier, temp_efficiency, shift_hours = 1.5, 0.8, 8.0
                permanent = {}
                for row in rows:
                    gap = max(0, target * row['required_hours'] - row['available_productive_hours'])
                    key = (row['site_id'], row['role_id'])
                    permanent[key] = max(permanent.get(key, 0), math.ceil(gap / (shift_hours * factor)))
                cost = residual = original = paid_total = 0.0
                details = []
                for row in rows:
                    gap = max(0, target * row['required_hours'] - row['available_productive_hours'])
                    original += gap
                    paid = added = incremental = 0.0
                    if option == 'overtime':
                        paid = min(gap / factor, row['scheduled_headcount'] * ot_daily_limit)
                        added = paid * factor
                        incremental = paid * row['median_hourly_wage'] * ot_multiplier
                    elif option == 'temporary_shifts':
                        paid = math.ceil(gap / (shift_hours * factor * temp_efficiency)) * shift_hours
                        added = paid * factor * temp_efficiency
                        incremental = paid * row['median_hourly_wage'] * temp_multiplier
                    elif option == 'extra_daily_positions':
                        paid = permanent[(row['site_id'], row['role_id'])] * shift_hours
                        added = paid * factor
                        incremental = paid * row['median_hourly_wage']
                    remaining = max(0, gap - added)
                    residual += remaining
                    cost += incremental
                    paid_total += paid
                    if gap > 0 or paid > 0:
                        details.append(dict(date=row['planning_date'], site=row['site_id'], role=row['role_id'],
                                            gap_productive_hours=gap, added_paid_hours=paid,
                                            residual_productive_hours=remaining, incremental_cost=incremental))
                assert residual <= original + 1e-8
                if option in ('temporary_shifts', 'extra_daily_positions'):
                    assert residual < 1e-8
                results.append(dict(productivity=case, service_target=target, option=option,
                                    initial_gap_hours=original, residual_gap_hours=residual,
                                    incremental_cost=cost, added_paid_hours=paid_total, actions=details))
    return results


if __name__ == '__main__':
    with sqlite3.connect(f'file:{ROOT / "data/workforce_planner.db"}?mode=ro', uri=True) as connection:
        results = compare(connection)
    output = ROOT / 'data/processed/staffing_option_comparison.json'
    output.write_text(json.dumps(results, indent=2) + '\n')
    for r in results:
        if r['productivity'] == 'base':
            print(f"{r['service_target']:.0%} {r['option']}: cost=${r['incremental_cost']:,.2f}, "
                  f"gap={r['initial_gap_hours']:.2f}, remaining={r['residual_gap_hours']:.2f}")
    print(f'Saved {len(results)} comparisons to {output}')
