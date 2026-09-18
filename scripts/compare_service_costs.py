"""Rank a finite policy grid under common service accounting and stress cases."""
import hashlib
import itertools
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from workforce_planner.service_scenarios import simulate
from workforce_planner.cost_policy import make_policy
from analyze_operational_actions import read_csv, segment_orders, write_csv


def main():
    config_path=ROOT/'config/footwear_scenarios.json'
    costs_path=ROOT/'config/staffing_cost_scenarios.json'
    source=ROOT/'data/raw/warehouse_picking/Customer_Order.csv'
    config=json.loads(config_path.read_text())
    costs=json.loads(costs_path.read_text())
    records=read_csv(source,';')
    demands={}
    for basis,rows in [('retained',records),('deduplicated_sensitivity',list({tuple(r.items()):r for r in records}.values()))]:
        demand=Counter()
        for r in segment_orders(rows):
            demand[date.fromisoformat(r['date'])]+=r['units']
        demands[basis]=demand
    results=[]
    for extra,ot,temps in itertools.product(costs['extra_permanent_workers'],costs['max_overtime_hours_per_present_worker'],costs['max_temporary_workers_per_day']):
        policy_id=f'extra{extra}_ot{ot}_temps{temps}'
        workers=costs['base_workers']+extra
        for basis,rate,absent,lead in itertools.product(demands,costs['stress_productivity_rates'],costs['stress_absent_workers'],costs['temporary_lead_operating_days']):
            policy=make_policy(workers,absent,rate,ot,temps,lead,config,costs)
            summary,daily=simulate(demands[basis],workers,absent,rate,costs['service_operating_days'],config,policy)
            regular=sum(r['regular_cost'] for r in daily)
            overtime=sum(r['overtime_cost'] for r in daily)
            temporary=sum(r['temporary_cost'] for r in daily)
            committed_shifts=policy.outstanding_shifts()
            commitment_cost=committed_shifts*config['paid_hours']*costs['temporary_hourly_cost']
            assert summary['arrivals']==sum(summary[k] for k in ['completed_on_time','completed_late','overdue_unfinished','pending_not_due'])
            results.append(dict(policy=policy_id,basis=basis,extra_workers=extra,ot_limit=ot,temp_limit=temps,lead_days=lead,
                                **summary,regular_cost=round(regular,2),overtime_cost=round(overtime,2),temporary_cost=round(temporary,2),
                                committed_future_temp_shifts=committed_shifts,
                                committed_future_temp_cost=round(commitment_cost,2),
                                total_cost=round(regular+overtime+temporary+commitment_cost,2),
                                overtime_paid_hours=sum(r['overtime_paid_hours'] for r in daily),
                                temporary_shifts=sum(r['temporary_workers'] for r in daily)))
    ranked=[]
    for policy_id in sorted({r['policy'] for r in results}):
        selected=[r for r in results if r['policy']==policy_id]
        base=next(r for r in selected if r['basis']=='retained' and r['rate']==40 and r['absent']==0 and r['lead_days']==1)
        ranked.append(dict(policy=policy_id,all_stresses_pass=all(r['target_met'] is True for r in selected),
                           passed_cases=sum(r['target_met'] is True for r in selected),tested_cases=len(selected),
                           worst_on_time_share=min(r['on_time_unit_share'] for r in selected),
                           base_cost=base['total_cost'],base_on_time_share=base['on_time_unit_share'],
                           worst_cost=max(r['total_cost'] for r in selected)))
    ranked.sort(key=lambda r:(not r['all_stresses_pass'],r['worst_cost'],r['policy']))
    out=ROOT/'data/processed/service_costs'
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/'cases.csv',results)
    write_csv(out/'policy_robustness.csv',ranked)
    base=[r for r in results if r['basis']=='retained' and r['rate']==40 and r['absent']==0 and r['lead_days']==1 and r['target_met'] is True]
    report=dict(cases=len(results),policies=len(ranked),
                lowest_base_cost_passing=min(base,key=lambda r:r['total_cost']) if base else None,
                lowest_worst_case_cost_robust=next((r for r in ranked if r['all_stresses_pass']),None),
                ranking='Among tested policies only. Robust means passes every listed stress, not a probability. Robust ranking minimizes maximum cost over tested stresses.',
                config=config,costs=costs,
                source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [config_path,costs_path,source]})
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('config','costs','source_hashes')},indent=2))


if __name__=='__main__':
    main()
