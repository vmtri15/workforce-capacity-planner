"""Profile downloaded research data without adopting rates as site calibration."""
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def stats(values):
    if not values:
        return {'count': 0}
    return dict(count=len(values), mean=round(statistics.mean(values), 3),
                median=round(statistics.median(values), 3), min=round(min(values), 3), max=round(max(values), 3))


def openpack():
    directory = RAW / 'openpack_timing'
    manifest = json.loads((directory / 'manifest.json').read_text())
    expected = read(RAW / 'openpack-dataset-main/release/v1.0.0/file_index/zenodo.csv')
    wanted = {r['path'] for r in expected if any('/'+s+'/' in r['path'] for s in
              ('openpack-operations', 'openpack-outliers', 'order-sheet')) and r['path'].endswith('.csv')}
    actual = {r['path'] for r in manifest}
    if wanted - actual:
        raise ValueError(f'Missing {len(wanted-actual)} timing files')
    scenarios = {}
    text = (RAW / 'openpack-dataset-main/docs/data-collection/sessions.md').read_text()
    for line in text.splitlines():
        fields = [v.strip() for v in line.split('|')]
        if len(fields)>4 and fields[1].startswith('U') and fields[2].startswith('S') and fields[3] in ('S1','S2','S3','S4'):
            scenarios[fields[1],fields[2]] = fields[3]
    # These are physical box-handling operations, not the full packing-station cycle.
    core = {'Assemble Box', 'Insert Items', 'Close Box', 'Attach Box Label', 'Attach Shipping Label'}
    by_operation, by_scenario, by_items = defaultdict(list), defaultdict(list), defaultdict(list)
    rows_out, unmatched, invalid, overlaps = [], [], 0, 0
    for path in sorted(directory.glob('*/annotation/openpack-operations/*.csv')):
        user, session = path.parts[-4], path.stem
        orders = read(directory / user / 'system/order-sheet' / path.name)
        lookup = {r['box']:r for r in orders}
        if len(lookup)!=len(orders):
            raise ValueError('Duplicate order box key')
        groups = defaultdict(list)
        operations = read(path)
        for r in operations:
            start,end = datetime.fromisoformat(r['start']),datetime.fromisoformat(r['end'])
            seconds = (end-start).total_seconds()
            if seconds<=0:
                invalid+=1
                continue
            by_operation[r['operation']].append(seconds)
            groups[r['box']].append((start,end,r['operation'],seconds))
        for box, intervals in groups.items():
            intervals.sort()
            overlaps += sum(b[0]<a[1] for a,b in zip(intervals,intervals[1:]))
            order = lookup.get(box)
            if order is None:
                unmatched.append([user,session,box])
            core_seconds = sum(i[3] for i in intervals if i[2] in core)
            scenario = scenarios.get((user,session),'unknown')
            result = dict(recording_id=user,session=session,box=box,scenario=scenario,
                          item_count=int(order['total_amount']) if order else None,
                          core_box_handling_seconds=round(core_seconds,3),
                          core_timing_review_required=core_seconds<=0,
                          annotated_operation_seconds=round(sum(i[3] for i in intervals),3),
                          elapsed_span_seconds=round((max(i[1] for i in intervals)-intervals[0][0]).total_seconds(),3))
            rows_out.append(result)
            by_scenario[scenario].append(core_seconds)
            if order:
                by_items[result['item_count']].append(core_seconds)
    output = ROOT / 'data/processed/openpack_box_timing.csv'
    with output.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows_out[0]));writer.writeheader();writer.writerows(rows_out)
    return dict(files=len(manifest), recording_ids=len({r['recording_id'] for r in rows_out}),
                distinct_people_documented=16, boxes=len(rows_out),
                sessions=len({(r['recording_id'],r['session']) for r in rows_out}),
                invalid_durations=invalid, overlapping_adjacent_intervals=overlaps, unmatched_boxes=unmatched,
                zero_core_box_records=[{k:r[k] for k in ('recording_id','session','box')} for r in rows_out if r['core_timing_review_required']],
                core_operations=sorted(core), core_seconds_by_scenario={k:stats(v) for k,v in by_scenario.items()},
                core_seconds_by_item_count={k:stats(v) for k,v in by_items.items()},
                operation_seconds={k:stats(v) for k,v in by_operation.items()},
                interpretation='Experimental reference, not calibrated warehouse productivity; incident annotations retained in raw data, not excluded from timing summaries.')


def jth():
    directory=RAW/'jth_data'
    history,jobs,candidates=[read(directory/name) for name in ('history.csv','jobs.csv','candidates.csv')]
    candidate_ids={r['candidate_id'] for r in candidates}; job_ids={r['job_id'] for r in jobs}
    dates=[k for k in history[0] if k.endswith('_date')]
    present=lambda v: bool(v and v.lower() not in ('nan','nat','none'))
    duration=[]; negative=0
    for row in history:
        a,b=row.get('job_offer_proposed_date'),row.get('job_offer_accepted_date')
        if present(a) and present(b):
            days=(datetime.fromisoformat(b)-datetime.fromisoformat(a)).days
            if days<0:negative+=1
            else:duration.append(days)
    return dict(history_rows=len(history),jobs=len(jobs),candidates=len(candidates),
                duplicate_application_ids=len(history)-len({r['application_id'] for r in history}),
                accepted_without_offer_date=sum(present(r['job_offer_accepted_date']) and not present(r['job_offer_proposed_date']) for r in history),
                duplicate_candidate_ids=len(candidates)-len(candidate_ids),duplicate_job_ids=len(jobs)-len(job_ids),
                unmatched_candidate_rows=sum(r['candidate_id'] not in candidate_ids for r in history),
                unmatched_job_rows=sum(r['job_id'] not in job_ids for r in history),
                date_present_counts={k:sum(present(r[k]) for r in history) for k in dates},
                last_stage_counts=dict(Counter(r.get('last_stage_reached') for r in history)),
                offer_to_acceptance_days=stats(duration),negative_offer_intervals=negative,
                history_columns=list(history[0]),
                interpretation='Privacy-altered dates from French recruiting; not warehouse hiring calibration or actual employee start dates.')


if __name__=='__main__':
    result=dict(openpack=openpack(),jth=jth())
    (ROOT/'data/processed/operational_research_profile.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
