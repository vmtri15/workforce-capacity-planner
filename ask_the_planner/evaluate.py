"""Score Ask the Planner on the 30 test questions, before and after adding the business glossary.

schema_only and glossary get the same model, instructions and schema; glossary adds glossary.md.
guided adds the fixes from FAILURE_REVIEW.md on top: base case views, the base case rule in the main
instructions, and worked examples (prompt.py). For each answerable question the last SQL result the model ran successfully is
compared with the hand checked answer (scoring.py). The two unanswerable questions are scored by a
simple rule (did the answer say the data cannot answer it) and flagged for a human to read.

Needs your Gemini key in the environment (GEMINI_API_KEY or GOOGLE_API_KEY). Run from the project root:
    .venv/bin/python ask_the_planner/build_eval_db.py      # once, builds the evaluation copy
    .venv/bin/python ask_the_planner/evaluate.py
Options: --limit 3 for a cheap trial run, --only Q12,Q15 for chosen questions, --fresh to start over,
--min-interval seconds between model calls (default 13, which keeps under the free tier's 5 calls a minute).
The run can stop and resume: every answer is saved to results/transcript.jsonl as it comes in, and a new
run skips questions that already have an answer. So a daily free quota can be spread over several days.
Outputs go to ask_the_planner/results/.
"""
import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from planner_agent import DEFAULT_MODEL, ask, build_planner
from readonly_sql import connect_read_only
from scoring import answer_mentions, frames_match

EVAL_DB = HERE / 'eval_db/planner_for_eval.db'
RESULTS = HERE / 'results'
CONDITIONS = {'schema_only': (False, False), 'glossary': (True, False), 'guided': (True, True)}  # (glossary, guided)
DECLINE = re.compile(r"cannot|can't|can not|not available|no data|does not (contain|have|include)|doesn't (contain|have|include)"
                     r"|unable|not possible|isn't (available|possible)|no information|not in the database|no (2023|hiring)", re.I)
FATAL = re.compile(r'NOT_FOUND|API key|API_KEY|PERMISSION_DENIED|UNAUTHENTICATED', re.I)
# Short names a manager would accept for the sites, used for every question.
NAME_ALIASES = {'joliet': ['Joliet'], 'ohare': ["O'Hare", 'Ohare'], 'kenosha': ['Kenosha'],
                'Joliet/Elwood': ['Joliet'], "O'Hare area": ["O'Hare", 'Ohare'], 'Kenosha/Pleasant Prairie': ['Kenosha']}
RATE_LIMIT = re.compile(r'429|RESOURCE_EXHAUSTED|quota|rate limit', re.I)
BUSY = re.compile(r'503|UNAVAILABLE|high demand|overloaded|timed out|timeout', re.I)  # a temporary outage, not a wrong answer


def gold_frames(question, database):
    connection = connect_read_only(database)
    try:
        return [pd.read_sql_query(sql, connection) for sql in [question['gold_sql'], *question.get('alt_sql', [])]]
    finally:
        connection.close()


def good_frames(queries):
    """The results of the queries that ran without an error, in order."""
    return [q['result'] for q in queries if q['error'] is None and q['result'] is not None]


def score(question, answer, frames, error, database):
    """The main score is the final answer a manager reads. The SQL checks are kept as extra detail."""
    if not question.get('answerable', True):
        declined = bool(DECLINE.search(answer or ''))
        return dict(passed=declined, reason='said it cannot answer' if declined else 'did not clearly decline',
                    sql_found=None, last_sql_match=None, needs_review=True)
    percent_ok = question.get('percent_ok', False)
    golds = gold_frames(question, database)
    aliases = {**NAME_ALIASES, **(question.get('answer_aliases') or {})}
    checks = [answer_mentions(answer, g, percent_ok, aliases) for g in golds]
    passed = any(ok for ok, _ in checks)
    reason = 'match' if passed else (error if not answer and error else checks[0][1])
    sql_found = any(frames_match(f, g, percent_ok)[0] for f in frames for g in golds)
    last_sql_match = bool(frames) and any(frames_match(frames[-1], g, percent_ok)[0] for g in golds)
    return dict(passed=passed, reason=reason, sql_found=sql_found, last_sql_match=last_sql_match, needs_review=False)


class QuotaStop(Exception):
    """The run cannot continue today: no credits, or the daily quota is used up."""


async def run_one(planner, question, retries=8):
    for attempt in range(retries):
        result = await ask(planner, question)
        error = result['error'] or ''  # only the error text: query results can contain numbers like 429
        if FATAL.search(error):
            sys.exit('Stopping: the Gemini API refused the request (wrong model name or key).\n' + error[:600])
        if BUSY.search(error) and not RATE_LIMIT.search(error):
            if attempt >= 3:  # a long outage is not a wrong answer: stop, and a later run resumes here
                raise QuotaStop('the model is overloaded (503). Run the same command later: finished questions are kept.')
            print(f'    model busy, waiting {30 * (attempt + 1)}s', flush=True)
            time.sleep(30 * (attempt + 1))
            continue
        if not RATE_LIMIT.search(error):
            return result
        if re.search(r'prepay|prepaid|credits? (are |were )?depleted', error, re.I):
            raise QuotaStop('the Gemini account has no credits left. Add credits in AI Studio billing, or use a key '
                            'from a project without billing (free tier).\n' + error[:600])
        if re.search(r'per ?day|PerDay|_per_day|limit: 0', error, re.I):
            raise QuotaStop('the daily quota for this model is used up. Run the same command tomorrow: finished '
                            'questions are kept and skipped.\n' + error[:600])
        hint = re.search(r'retry in ([\d.]+)s', error)
        wait = float(hint.group(1)) + 2 if hint else 60
        print(f'    per minute limit reached, waiting {wait:.0f}s', flush=True)
        time.sleep(wait)
    return result


def preview(frame, n=5):
    return None if frame is None else frame.head(n).to_dict('records')


async def main():
    logging.getLogger('vanna').propagate = False  # errors are kept in the results, not printed as tracebacks
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=str(EVAL_DB))
    parser.add_argument('--limit', type=int)
    parser.add_argument('--only')
    parser.add_argument('--min-interval', type=float, default=13.0)
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--rescore', action='store_true', help='score the saved answers again, no API calls')
    parser.add_argument('--model')
    parser.add_argument('--fake', action='store_true', help='answer with the gold SQL, no API calls: checks the runner and scoring')
    args = parser.parse_args()
    database = Path(args.db)
    if not database.exists():
        sys.exit(f'{database} not found. Run: .venv/bin/python ask_the_planner/build_eval_db.py')
    questions = yaml.safe_load((HERE / 'questions.yaml').read_text())
    if args.only:
        questions = [q for q in questions if q['id'] in args.only.split(',')]
    if args.limit:
        questions = questions[:args.limit]
    global RESULTS
    if args.fake:
        RESULTS = HERE / '.run_data/fake_results'  # a dry run never overwrites the real results
    RESULTS.mkdir(parents=True, exist_ok=True)
    transcript = RESULTS / 'transcript.jsonl'
    if args.fresh and transcript.exists():
        transcript.unlink()
    if args.rescore:
        rescore(transcript, database)
        write_summary(transcript, questions, args.fake)
        return
    done = {(r['id'], r['condition']) for r in read_transcript(transcript)}
    stopped = None
    try:
        for condition, (use_glossary, guided) in CONDITIONS.items():
            planner = None
            for q in questions:
                if (q['id'], condition) in done:
                    continue
                print(f"{condition:12} {q['id']} {q['question']}", flush=True)
                if args.fake:
                    from scripted_llm import ScriptedLlm
                    planner = build_planner(database, use_glossary=use_glossary, guided=guided,
                                            llm=ScriptedLlm(q.get('gold_sql') or 'SELECT 1', q.get('expected', '')))
                elif planner is None:
                    planner = build_planner(database, use_glossary=use_glossary, guided=guided, model=args.model)
                    planner.agent.llm_service.min_interval = args.min_interval
                result = await run_one(planner, q['question'])
                s = score(q, result['answer'], good_frames(result['queries']), result['error'], database)
                good = [x for x in result['queries'] if x['error'] is None]
                record = dict(id=q['id'], category=q['category'], answerable=q.get('answerable', True), condition=condition,
                              **s, queries_run=len(result['queries']), final_sql=good[-1]['sql'] if good else None,
                              question=q['question'], expected=q.get('expected'), answer=result['answer'], error=result['error'],
                              model=args.model or os.getenv('GEMINI_MODEL', DEFAULT_MODEL),
                              at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                              queries=[dict(sql=x['sql'], error=x['error'], rows=preview(x['result'], 50)) for x in result['queries']])
                with transcript.open('a') as f:
                    f.write(json.dumps(record, default=str) + '\n')
                print(f"    {'PASS' if s['passed'] else 'FAIL'}  {s['reason']}", flush=True)
                if result['error']:
                    print(f"    error: {result['error'][:300]}", flush=True)
    except QuotaStop as stop:
        stopped = str(stop)
    write_summary(transcript, questions, args.fake)
    if stopped:
        print('\nStopped early: ' + stopped)


def rescore(transcript, database):
    questions = {q['id']: q for q in yaml.safe_load((HERE / 'questions.yaml').read_text())}
    records = read_transcript(transcript)
    for r in records:
        frames = [pd.DataFrame(x.get('rows') or x.get('preview') or []) for x in r['queries'] if x['error'] is None]
        r.update(score(questions[r['id']], r['answer'], frames, r['error'], database))
    transcript.write_text(''.join(json.dumps(r, default=str) + '\n' for r in records))
    print(f'Rescored {len(records)} saved answers.')


def read_transcript(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def changed(pivot, before, after, now_passes):
    """Questions that pass in one condition and fail in the other."""
    if before not in pivot or after not in pivot:
        return []
    both = pivot[[before, after]].dropna()
    return sorted(both.index[(both[after] == now_passes) & (both[before] == (not now_passes))].tolist())


def write_summary(transcript, questions, fake):
    ids = {q['id'] for q in questions}
    records = {}
    for r in read_transcript(transcript):
        if r['id'] in ids:
            records[r['id'], r['condition']] = r  # the latest answer for each question and condition
    if not records:
        return
    table = pd.DataFrame([{k: v for k, v in r.items() if k != 'queries'} for r in records.values()])
    table.sort_values(['condition', 'id']).to_csv(RESULTS / 'eval_results.csv', index=False)
    answerable = table[table['answerable']]
    by_condition = answerable.groupby('condition')['passed'].agg(['sum', 'count'])
    pivot = answerable.pivot(index='id', columns='condition', values='passed')
    summary = dict(
        fake=fake, models=sorted(table['model'].unique().tolist()), answered=len(table), of=len(questions) * len(CONDITIONS),
        accuracy_answerable={c: dict(correct=int(r['sum']), of=int(r['count']), share=round(r['sum'] / r['count'], 3))
                             for c, r in by_condition.iterrows()},
        sql_found_answerable=answerable.groupby('condition')['sql_found'].mean().round(3).to_dict(),
        accuracy_by_category={c: g.groupby('condition')['passed'].mean().round(3).to_dict() for c, g in answerable.groupby('category')},
        fixed_by_glossary=changed(pivot, 'schema_only', 'glossary', True),
        broken_by_glossary=changed(pivot, 'schema_only', 'glossary', False),
        fixed_by_guidance=changed(pivot, 'glossary', 'guided', True),
        broken_by_guidance=changed(pivot, 'glossary', 'guided', False),
        unanswerable=table[~table['answerable']][['id', 'condition', 'passed', 'answer']].to_dict('records'))
    (RESULTS / 'summary.json').write_text(json.dumps(summary, indent=2, default=str) + '\n')
    print(json.dumps({k: summary[k] for k in ('answered', 'of', 'accuracy_answerable', 'sql_found_answerable', 'fixed_by_glossary', 'fixed_by_guidance', 'broken_by_guidance')}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
