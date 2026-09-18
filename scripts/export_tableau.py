"""Export aggregate-only Tableau inputs with explicit grains and stable keys."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from analyze_operational_actions import ROOT, read_csv, write_csv


def main():
    processed=ROOT/'data/processed'
    out=ROOT/'tableau/data'
    out.mkdir(parents=True,exist_ok=True)
    inputs=[]

    def read(relative):
        p=processed/relative
        inputs.append(p)
        return read_csv(p)

    tables={}
    daily=[]
    for basis in ['retained','deduplicated_sensitivity']:
        groups=defaultdict(lambda:dict(orders=0,units=0))
        source=read(f'operational_actions/orders_{basis}.csv')
        for r in source:
            g=groups[(r['date'],r['segment'])]
            g['orders']+=1
            g['units']+=int(r['units'])
        for (day,segment),v in sorted(groups.items()):
            daily.append(dict(demand_key=f'{basis}|{day}|{segment}',basis=basis,date=day,
                              segment=segment,**v,evidence='Observed source aggregation; duplicate interpretation varies'))
        assert sum(v['orders'] for (d,s),v in groups.items())==len(source)
    tables['demand_daily']=daily
    policies={}
    cases=[]
    metrics=['workers','absent','present_workers','rate','service_days','arrivals','completed_on_time',
             'completed_late','overdue_unfinished','pending_not_due','on_time_unit_share','target_met',
             'peak_backlog','backlog_unit_days','total_cost']
    periods=[('full','service_costs/cases.csv','2023-01-05','2023-10-19','2023-11-16'),
             ('selection','recommendation_validation/selection_cases.csv','2023-01-05','2023-06-30','2023-07-28'),
             ('evaluation','recommendation_validation/evaluation_cases.csv','2023-07-03','2023-10-19','2023-11-16')]
    for period,path,start,end,cost_end in periods:
        for r in read(path):
            if period=='full':
                policies[r['policy']]=dict(policy=r['policy'],scheduled_workers=int(r['workers']),
                    extra_workers=int(r['extra_workers']),ot_limit=int(r['ot_limit']),temp_limit=int(r['temp_limit']))
            key='|'.join([period,r['policy'],r['basis'],r['rate'],r['absent'],r['lead_days']])
            case=dict(case_key=key,period=period,policy=r['policy'],basis=r['basis'],
                      lead_days=int(r['lead_days']),demand_start=start,demand_end=end,cost_end=cost_end,
                      target_share=.95,evidence='Hypothetical historical replay',**{k:r[k] for k in metrics})
            assert int(r['arrivals'])==sum(int(r[k]) for k in ['completed_on_time','completed_late','overdue_unfinished','pending_not_due'])
            cases.append(case)
    tables['scenario_results']=cases
    tables['policies']=[policies[k] for k in sorted(policies)]
    assert all(r['policy'] in policies for r in cases)
    prices=read('recommendation_validation/price_sensitivity.csv')
    tables['price_sensitivity']=[dict(price_key=f"{r['wage']}|{r['overtime_multiplier']}|{r['temporary_rate']}",**r) for r in prices]
    products=read('operational_actions/monthly_top_references.csv')
    tables['monthly_top_products']=[dict(product_key=f"{r['month']}|{r['reference']}",basis='retained',**r) for r in products]
    keys=dict(demand_daily='demand_key',scenario_results='case_key',policies='policy',price_sensitivity='price_key',monthly_top_products='product_key')
    for name,rows in tables.items():
        assert len({r[keys[name]] for r in rows})==len(rows),name
        write_csv(out/f'{name}.csv',rows)
    manifest=dict(tables={name:dict(rows=len(rows),primary_key=keys[name],sha256=hashlib.sha256((out/f'{name}.csv').read_bytes()).hexdigest()) for name,rows in tables.items()},
                  sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  publication='Prepared locally only; not uploaded. No order, customer, employee IDs or credentials exported.',
                  source_attribution='Rodrigo Furlan de Assis, Order Picking Dataset from a Warehouse of a Footwear Manufacturing Company, DOI 10.17632/pf2w725pw3.1, CC BY 4.0. Aggregated and modeled transformations; no endorsement.',
                  relationships=[dict(left='scenario_results',right='policies',key='policy',cardinality='many-to-one')])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest['tables'],indent=2))


if __name__=='__main__':
    main()
