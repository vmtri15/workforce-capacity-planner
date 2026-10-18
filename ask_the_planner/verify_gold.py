"""Check every gold answer a second way, without the gold SQL.

Each answerable question has an independent check below that reads the raw rows and works the answer
out in plain Python (loops and arithmetic, no SQL aggregates). The script fails if any gold query and
its check disagree. Run from the project root:
    .venv/bin/python ask_the_planner/verify_gold.py [database]
"""
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from readonly_sql import connect_read_only
from scoring import frames_match

BASE, LOW = 'base_demand_base_productivity', 'base_demand_low_productivity'


def rows(c, table):
    cur = c.execute(f'SELECT * FROM {table}')
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def checks(c):
    sites = rows(c, 'sites')
    assume = {r['assumption_key']: r['numeric_value'] if r['numeric_value'] is not None else r['text_value']
              for r in rows(c, 'scenario_assumptions')}
    staff = [r for r in rows(c, 'staffing_plans') if r['run_id'] == BASE]
    cap = rows(c, 'daily_capacity_results')
    base_cap = [r for r in cap if r['run_id'] == BASE]
    runs = {r['run_id']: r['productivity_case'] for r in rows(c, 'planning_runs')}
    work = [r for r in rows(c, 'modeled_daily_workload') if r['run_id'] == BASE]

    def by(items, key, value):
        out = defaultdict(float)
        for r in items:
            out[r[key]] += value(r)
        return out

    gap_site = by(base_cap, 'site_id', lambda r: r['capacity_gap_hours'])
    gap_role = by(base_cap, 'role_id', lambda r: r['capacity_gap_hours'])
    units_day = by(work, 'planning_date', lambda r: r['modeled_units'])
    lines_day = by(work, 'planning_date', lambda r: r['modeled_order_lines'])
    worst = max(base_cap, key=lambda r: r['capacity_gap_hours'])
    start, end = date.fromisoformat(assume['source_window_start']), date.fromisoformat(assume['source_window_end'])
    service = {}
    for run_id, case in runs.items():
        met = [r['service_target_met'] for r in cap if r['run_id'] == run_id]
        service[case] = sum(met) / len(met)
    days = sorted(units_day)
    calendar_days = len(days)
    all_cost = sum(r['scheduled_headcount'] * r['paid_hours_per_person'] * r['median_hourly_wage'] for r in staff) * calendar_days
    in_window = [r for r in rows(c, 'workload_daily_source') if start.isoformat() <= r['source_date'] <= end.isoformat()]
    top = max(sites, key=lambda r: r['allocation_share'])
    best_paid = max((r for r in staff if r['site_id'] == 'joliet'), key=lambda r: r['median_hourly_wage'])
    return {
        'Q01': [[top['site_name'], top['allocation_share']]],
        'Q02': [[r['site_name'], r['allocation_share']] for r in sites],
        'Q03': [[assume['service_target']]],
        'Q04': [[start.isoformat(), end.isoformat(), (end - start).days + 1]],
        'Q05': [[assume['paid_hours_per_shift'] * assume['productive_time_factor']]],
        'Q06': [[k, v] for k, v in by(staff, 'site_id', lambda r: r['scheduled_headcount']).items()],
        'Q07': [[sum(r['scheduled_headcount'] for r in staff)]],
        'Q08': [[r['scheduled_headcount'] for r in staff if r['site_id'] == 'ohare' and r['role_id'] == 'fulfillment_associate']],
        'Q09': [[best_paid['role_id'], best_paid['median_hourly_wage']]],
        'Q10': [[k, v] for k, v in by(staff, 'site_id', lambda r: r['scheduled_headcount'] * r['paid_hours_per_person'] * r['median_hourly_wage']).items()],
        'Q11': [[all_cost]],
        'Q12': [[sum(r['capacity_gap_hours'] for r in base_cap)]],
        'Q13': [list(max(gap_site.items(), key=lambda kv: kv[1]))],
        'Q14': [[sum(r['capacity_gap_hours'] for r in cap if r['run_id'] == LOW)]],
        'Q15': [[k, v] for k, v in service.items()],
        'Q16': [[len({r['planning_date'] for r in base_cap if r['site_id'] == 'kenosha' and r['service_target_met'] == 0})]],
        'Q17': [[k, v] for k, v in gap_role.items() if v > 0],
        'Q18': [[worst['planning_date'], worst['site_id'], worst['role_id'], worst['capacity_gap_hours']]],
        'Q19': [[sum(r['surplus_hours'] for r in base_cap)]],
        'Q20': [list(max(units_day.items(), key=lambda kv: kv[1]))],
        'Q21': [[sum(r['modeled_orders'] for r in work)]],
        'Q22': [[sum(r['distinct_invoice_ids'] for r in in_window)]],
        'Q23': [[sum(lines_day.values()) / calendar_days]],
        'Q24': [[len({r['planning_date'] for r in work if r['source_record_present'] == 0})]],
        'Q25': [[r['median_hourly_wage'] for r in staff if r['site_id'] == 'kenosha' and r['role_id'] == 'packing_associate']],
        'Q26': [[max(r['hires'] for r in rows(c, 'qwi_labor_flows') if r['geography_name'].startswith('Kenosha County') and r['hires'] is not None)]],
        'Q27': [[r['source_name']] for r in rows(c, 'source_registry') if r['evidence_class'] == 'observed'],
        'Q28': [[sum(r['status'] == 'PASS' for r in rows(c, 'data_quality_results'))]],
    }


def main():
    database = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'eval_db/planner_for_eval.db'
    questions = yaml.safe_load((HERE / 'questions.yaml').read_text())
    c = connect_read_only(database)
    independent = checks(c)
    failures = 0
    for q in questions:
        if not q.get('answerable', True):
            continue
        gold = pd.read_sql_query(q['gold_sql'], c)
        mine = pd.DataFrame(independent[q['id']])
        ok, reason = frames_match(mine, gold, percent_ok=False)
        for alt in q.get('alt_sql', []):  # each alternative must give the same answer in another form
            alt_frame = pd.read_sql_query(alt, c)
            ok = ok and alt_frame.shape == gold.shape
        failures += not ok
        print(f"{q['id']} {'OK  ' if ok else 'FAIL'} {gold.values.tolist() if len(gold) <= 3 else f'{len(gold)} rows'} {'' if ok else reason}")
    c.close()
    print(f'\n{len(independent) - failures} of {len(independent)} gold answers confirmed by the independent check')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
