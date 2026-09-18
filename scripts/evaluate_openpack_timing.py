"""Person-held-out evaluation of experimental packing time estimates."""
import csv
import hashlib
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/processed/openpack_timing_audit.csv'


def summary(rows):
    values=[r['seconds'] for r in rows]
    return dict(boxes=len(rows),people=len({r['person_id'] for r in rows}),
                mean_seconds=round(st.mean(values),3),median_seconds=round(st.median(values),3)) if rows else dict(boxes=0,people=0)


def fit(rows):
    slope,intercept=st.linear_regression([r['items'] for r in rows],[r['seconds'] for r in rows])
    return intercept,slope


def main():
    with SOURCE.open() as f:
        rows=[r | dict(items=int(r['item_count']),seconds=float(r['station_seconds_excluding_picking'])) for r in csv.DictReader(f)]
    eligible=[r for r in rows if r['screen_pass']=='True' and abs(float(r['gap_seconds']))<=.001 and 1<=r['items']<=5]
    results={};predictions=[]
    for scenario in sorted({r['scenario'] for r in rows}):
        selected=[r for r in eligible if r['scenario']==scenario]
        people=sorted({r['person_id'] for r in selected})
        folds=[]
        for person in people:
            train=[r for r in selected if r['person_id']!=person]
            test=[r for r in selected if r['person_id']==person]
            assert set(r['person_id'] for r in train).isdisjoint(r['person_id'] for r in test)
            intercept,slope=fit(train);constant=st.mean(r['seconds'] for r in train)
            errors=defaultdict(list)
            for r in test:
                linear=intercept+slope*r['items']
                errors['constant'].append(abs(constant-r['seconds']))
                errors['item_count'].append(abs(linear-r['seconds']))
                predictions.append(dict(scenario=scenario,person_id=person,session=r['session'],box=r['box'],
                    item_count=r['items'],actual_seconds=r['seconds'],constant_seconds=round(constant,3),
                    item_count_seconds=round(linear,3)))
            folds.append(dict(person_id=person,boxes=len(test),
                              constant_mae=st.mean(errors['constant']),item_count_mae=st.mean(errors['item_count'])))
        intercept,slope=fit(selected)
        scenario_predictions=[r for r in predictions if r['scenario']==scenario]
        results[scenario]=dict(eligible=summary(selected),all_records=summary([r for r in rows if r['scenario']==scenario]),
            by_item_count={n:summary([r for r in selected if r['items']==n]) for n in range(1,6)},
            by_person={p:summary([r for r in selected if r['person_id']==p]) for p in people},
            exploratory_fit=dict(fixed_seconds=round(intercept,3),seconds_per_item=round(slope,3)),
            person_held_out_mae_seconds={model:round(st.mean(f[model+'_mae'] for f in folds),3) for model in ('constant','item_count')},
            box_weighted_held_out_mae_seconds={model:round(st.mean(abs(r[model+'_seconds']-r['actual_seconds']) for r in scenario_predictions),3) for model in ('constant','item_count')},
            folds=folds)
    report=dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                method='Leave one distinct person out within each scenario; fixed plus item-count ordinary least squares versus training-mean constant.',
                target='Annotated packing-station seconds excluding Picking; no paid-time allowance.',
                eligibility='Screen pass, no elapsed gap above 1 ms, 1-5 items.',
                total_eligible=len(eligible),excluded=len(rows)-len(eligible),scenarios=results,
                limits=['Experimental reference only; item count does not control box size or work location.',
                        'Filtering incidents and gaps can bias times downward; all-record means are descriptive comparisons, not causal estimates.',
                        'Exploratory cross-validation is not a final independent deployment test.',
                        'Do not extrapolate to 12/24/48-unit jobs or interpret station-local Picking as warehouse route picking.'])
    output=ROOT/'data/processed/openpack_timing_evaluation.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    with (ROOT/'data/processed/openpack_held_out_predictions.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(predictions[0]));writer.writeheader();writer.writerows(predictions)
    print(json.dumps({s:{k:v for k,v in r.items() if k not in ('by_item_count','by_person','folds')} for s,r in results.items()},indent=2))


if __name__=='__main__':
    main()
