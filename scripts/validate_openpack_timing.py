"""Audit experimental timing boundaries; do not calibrate warehouse rates."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from profile_operational_research import read, stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/openpack_timing'
CORE = {'Assemble Box', 'Insert Items', 'Close Box', 'Attach Box Label', 'Attach Shipping Label'}
STATION = CORE | {'Relocate Item Label', 'Scan Label', 'Fill out Order', 'Put on Back Table'}
ALIASES = {'U0202':'U0105','U0203':'U0108','U0204':'U0110','U0205':'U0107','U0210':'U0103'}


def interval(row):
    return datetime.fromisoformat(row['start']), datetime.fromisoformat(row['end'])


def main():
    manifest = json.loads((RAW/'manifest.json').read_text())
    for entry in manifest:
        if hashlib.sha256((RAW/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError(f"Input changed: {entry['path']}")
    summaries = {(r['recording_id'],r['session'],r['box']):r for r in read(ROOT/'data/processed/openpack_box_timing.csv')}
    output=[]
    for path in sorted(RAW.glob('*/annotation/openpack-operations/*.csv')):
        user,session=path.parts[-4],path.stem
        events=read(RAW/user/'annotation/openpack-outliers'/path.name)
        groups=defaultdict(list)
        for row in read(path):
            groups[row['box']].append(row)
        for box, rows in groups.items():
            base=summaries[user,session,box]
            spans=sorted(interval(r) for r in rows)
            start,end=min(s[0] for s in spans),max(s[1] for s in spans)
            labels={r['operation'] for r in rows}
            matched=[e for e in events if any(interval(e)[0]<b and interval(e)[1]>a for a,b in spans)]
            incidents=[e for e in matched if e['category'] in {'Incident','Recovery'}]
            durations=defaultdict(float)
            for r in rows:
                a,b=interval(r)
                durations[r['operation']]+=(b-a).total_seconds()
            missing=sorted(CORE-labels)
            flags=[]
            if missing: flags.append('missing_core_labels')
            if incidents: flags.append('incident_or_recovery_overlap')
            if labels & {'Null','System Error'}: flags.append('nonwork_or_error_label')
            # Missing labels can reflect preassembled boxes, not necessarily corrupt data.
            output.append(dict(recording_id=user,person_id=ALIASES.get(user,user),session=session,
                box=box,scenario=base['scenario'],item_count=int(base['item_count']),
                station_seconds_excluding_picking=round(sum(durations[k] for k in STATION),3),
                picking_seconds=round(durations['Picking'],3),
                nonwork_or_error_seconds=round(durations['Null']+durations['System Error'],3),
                elapsed_seconds=round((end-start).total_seconds(),3),
                gap_seconds=round((end-start).total_seconds()-sum(durations.values()),3),
                missing_core_labels=';'.join(missing),incident_count=len(incidents),
                annotation_event_count=len(matched),
                annotation_categories=';'.join(sorted({e['category'] for e in matched})),
                review_flags=';'.join(flags),screen_pass=not flags))
    target=ROOT/'data/processed/openpack_timing_audit.csv'
    with target.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    grouped=defaultdict(list)
    for r in output:
        if r['screen_pass']:
            grouped[r['scenario']].append(r['station_seconds_excluding_picking'])
    result=dict(boxes=len(output),distinct_people=len({r['person_id'] for r in output}),
        screen_pass=sum(r['screen_pass'] for r in output),
        incident_overlap_boxes=sum(r['incident_count']>0 for r in output),
        missing_core_boxes=sum(bool(r['missing_core_labels']) for r in output),
        nonwork_or_error_boxes=sum(r['nonwork_or_error_seconds']>0 for r in output),
        positive_gap_boxes=sum(r['gap_seconds']>0.001 for r in output),
        negative_gap_boxes=sum(r['gap_seconds']<-.001 for r in output),
        screen_pass_station_seconds_by_scenario={k:stats(v) for k,v in grouped.items()},
        review_examples=[r for r in output if r['missing_core_labels']][:5],
        station_operations=sorted(STATION),
        limitations=['Screen pass is an annotation-quality screen, not proof of a complete production cycle.',
          'Excluding incidents selects easier work and may understate operational labor.',
          'Picking is kept separate to prevent double counting; its experimental meaning must match the target workflow.',
          'Missing core labels may represent preassembled boxes or truncated recordings; do not automatically delete.',
          'No break allowance or site productivity calibration applied.'])
    (ROOT/'data/processed/openpack_timing_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='review_examples'},indent=2))


if __name__=='__main__':
    main()
