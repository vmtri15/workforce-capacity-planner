"""Audit recruitment-stage evidence without adopting warehouse hiring rates."""
import csv
import hashlib
import json
import statistics as st
from collections import Counter
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/jth_data'
STAGES=['spontaneous_application_date','shortlist_date','qualification_date',
        'resume_sent_to_company_date','1st_interview_date','2nd_interview_date',
        '3rd_interview_date','4th_interview_date','job_offer_proposed_date','job_offer_accepted_date']
TERMS=('warehouse','logistic','supply chain','entrepot','entrepôt','magasinier','packer','packing','order picker')


def read(name):
    with (RAW/name).open(newline='') as f:
        return list(csv.DictReader(f))


def present(value):
    return bool(value and value.lower() not in ('nan','nat','none'))


def main():
    jobs,history=read('jobs.csv'),read('history.csv')
    invalid=0;parsed=[];reversed_rows=0;end_before_last=0
    for row in history:
        dates={}
        for key in STAGES+['end_of_process_date']:
            if present(row[key]):
                try: dates[key]=date.fromisoformat(row[key])
                except ValueError: invalid+=1
        sequence=[dates[k] for k in STAGES if k in dates]
        reversed_rows+=any(b<a for a,b in zip(sequence,sequence[1:]))
        end_before_last+=bool(sequence and 'end_of_process_date' in dates and dates['end_of_process_date']<max(sequence))
        parsed.append(dates)
    intervals={}
    for a,b in [('spontaneous_application_date','job_offer_accepted_date'),
                ('shortlist_date','job_offer_accepted_date'),
                ('job_offer_proposed_date','job_offer_accepted_date')]:
        values=[(d[b]-d[a]).days for d in parsed if a in d and b in d]
        nonnegative=[v for v in values if v>=0]
        intervals[a+' -> '+b]=dict(paired_records=len(values),negative=sum(v<0 for v in values),
            same_day=sum(v==0 for v in values),median_days=st.median(nonnegative) if nonnegative else None,
            mean_days=round(st.mean(nonnegative),3) if nonnegative else None,
            max_days=max(nonnegative) if nonnegative else None)
    coverage={}
    for name,fields in [('manual_category',['job_category','expertise_area']),
                        ('llm_category',['llm_job_category','llm_expertise_area']),
                        ('llm_industry',['llm_industry_domains'])]:
        selected=[r for r in jobs if any(t in ' '.join(r[k] for k in fields).lower() for t in TERMS)]
        ids={r['job_id'] for r in selected}
        coverage[name]=dict(keyword_matched_jobs=len(ids),linked_histories=sum(r['job_id'] in ids for r in history),
            category_examples=[{k:r[k] for k in fields} for r in selected[:10]])
    result=dict(job_count=len(jobs),history_count=len(history),
        blank_manual_job_categories=sum(not present(r['job_category']) for r in jobs),
        top_manual_categories=Counter(r['job_category'] for r in jobs if present(r['job_category'])).most_common(15),
        keyword_screen_terms=TERMS,role_coverage=coverage,
        invalid_dates=invalid,rows_with_reversed_observed_stages=reversed_rows,end_before_last_observed_stage=end_before_last,
        stage_date_counts={k:sum(k in d for d in parsed) for k in STAGES},intervals=intervals,
        missing_end_date=sum('end_of_process_date' not in d for d in parsed),
        input_hashes={name:hashlib.sha256((RAW/name).read_bytes()).hexdigest() for name in ('jobs.csv','history.csv','dataset_card.md')},
        decision='Use for generic recruiting-funnel workflow only; do not calibrate warehouse hiring lead times.',
        limitations=['Keyword screening does not establish absence of warehouse jobs; manual categories are often missing.',
            'LLM-derived industries and categories are not verified role classifications.',
            'Five-day-scale privacy noise distorts elapsed durations; same-day values are not exact measured durations.',
            'Unobserved stages do not imply rejection, zero duration or a completed process.',
            'Offer acceptance is not a start date or productive readiness date.',
            'Endpoint-paired durations are selected subsets, not population time-to-hire estimates.'])
    (ROOT/'data/processed/jth_recruiting_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
