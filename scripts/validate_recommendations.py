"""Price sensitivity and exploratory chronological policy validation."""
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from datetime import date

from compare_service_costs import ROOT, make_policy, simulate, read_csv, segment_orders, write_csv


def choose(rows, robust):
    groups=defaultdict(list)
    for r in rows:
        if robust or (r['basis']=='retained' and r['rate']==40 and r['absent']==0 and r['lead_days']==1):
            groups[r['policy']].append(r)
    eligible=[(max(r['total_cost'] for r in values),key) for key,values in groups.items()
              if all(r['target_met'] is True for r in values)]
    return min(eligible)[1] if eligible else None


def price(row, wage, premium, temp_rate, hours):
    return round(row['regular_paid_hours']*wage + row['overtime_paid_hours']*wage*premium
                 + row['temporary_shifts']*hours*temp_rate,2)


def main():
    config=json.loads((ROOT/'config/footwear_scenarios.json').read_text())
    costs=json.loads((ROOT/'config/staffing_cost_scenarios.json').read_text())
    original=json.loads((ROOT/'data/processed/service_costs/summary.json').read_text())
    for relative,expected in original['source_hashes'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
            raise ValueError('Stale cost cases; rerun compare_service_costs.py')
    out=ROOT/'data/processed/recommendation_validation'
    out.mkdir(parents=True,exist_ok=True)
    old=[]
    for r in read_csv(ROOT/'data/processed/service_costs/cases.csv'):
        old.append(dict(policy=r['policy'],basis=r['basis'],rate=float(r['rate']),absent=int(r['absent']),
                        lead_days=int(r['lead_days']),target_met=r['target_met']=='True',
                        regular_paid_hours=float(r['regular_cost'])/costs['regular_hourly_cost'],
                        overtime_paid_hours=int(r['overtime_paid_hours']),
                        temporary_shifts=int(r['temporary_shifts'])+int(r['committed_future_temp_shifts'])))
    prices=[]
    for wage,premium,temp_rate in itertools.product([18,22,28],[1.25,1.5,2],[24,30,40]):
        priced=[r | dict(total_cost=price(r,wage,premium,temp_rate,config['paid_hours'])) for r in old]
        prices.append(dict(wage=wage,overtime_multiplier=premium,temporary_rate=temp_rate,
                           base_choice=choose(priced,False),robust_choice=choose(priced,True)))
    write_csv(out/'price_sensitivity.csv',prices)

    raw=read_csv(ROOT/'data/raw/warehouse_picking/Customer_Order.csv',';')
    demands={}
    cutoff=date(2023,7,1)
    for basis,records in [('retained',raw),('deduplicated_sensitivity',list({tuple(r.items()):r for r in raw}.values()))]:
        demand=Counter()
        for r in segment_orders(records):
            demand[date.fromisoformat(r['date'])]+=r['units']
        demands[basis]=demand
    options={f'extra{e}_ot{o}_temps{t}':(costs['base_workers']+e,o,t)
             for e,o,t in itertools.product(costs['extra_permanent_workers'],
                 costs['max_overtime_hours_per_present_worker'],costs['max_temporary_workers_per_day'])}

    def run(period, selected):
        results=[]
        for key in selected:
            workers,ot,temps=options[key]
            for basis,rate,absent,lead in itertools.product(demands,costs['stress_productivity_rates'],costs['stress_absent_workers'],costs['temporary_lead_operating_days']):
                demand={d:q for d,q in demands[basis].items() if (d<cutoff)==(period=='selection')}
                policy=make_policy(workers,absent,rate,ot,temps,lead,config,costs)
                summary,daily=simulate(demand,workers,absent,rate,costs['service_operating_days'],config,policy)
                total=sum(r['regular_cost']+r['overtime_cost']+r['temporary_cost'] for r in daily)
                total+=policy.outstanding_shifts()*config['paid_hours']*costs['temporary_hourly_cost']
                results.append(dict(period=period,policy=key,basis=basis,lead_days=lead,**summary,total_cost=round(total,2)))
        return results
    training=run('selection',options)
    selected=dict(base=choose(training,False),robust=choose(training,True))
    testing=run('evaluation',sorted({v for v in selected.values() if v}))
    exploratory=run('evaluation',options)
    write_csv(out/'selection_cases.csv',training)
    if testing:
        write_csv(out/'evaluation_cases.csv',testing)
    write_csv(out/'exploratory_replacement_cases.csv',exploratory)
    evaluation={}
    for objective,key in selected.items():
        cases=[r for r in testing if r['policy']==key]
        if objective=='base':
            cases=[r for r in cases if r['basis']=='retained' and r['rate']==40 and r['absent']==0 and r['lead_days']==1]
        evaluation[objective]=dict(policy=key,cases=len(cases),passed=sum(r['target_met'] is True for r in cases),
                                  worst_service=min((r['on_time_unit_share'] for r in cases),default=None))
    exploratory_replacement={
        'base': choose(exploratory,False),
        'robust': choose(exploratory,True),
    }
    report=dict(price_grid=prices,price_winners=dict(base=dict(Counter(r['base_choice'] for r in prices)),
                 robust=dict(Counter(r['robust_choice'] for r in prices))),selection=selected,evaluation=evaluation,
                 exploratory_replacement=exploratory_replacement,
                 split='Select on creation dates before 2023-07-01; evaluate frozen selected policies on dates from 2023-07-01 onward.',
                 caveats=['Exploratory chronological check: full dataset was previously inspected, not untouched validation.',
                          'Independent periods each reset backlog/bookings to zero and append 28 zero-arrival recovery days.',
                          'Earlier-period recovery is artificial and does not consume later-period arrivals.',
                          'Cost repricing holds reactive policy behavior fixed because triggers do not depend on prices.',
                          'Frozen-policy validation was not retuned after later months; exploratory replacements use the later period and are not fresh holdout results.',
                          'The 27 illustrative prices are not market quotes.'],
                 source_hashes=original['source_hashes'])
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['price_winners','selection','evaluation','exploratory_replacement']},indent=2))


if __name__=='__main__':
    main()
