"""Ask the planner database a question in plain English.

    export GEMINI_API_KEY="your key"
    .venv/bin/python ask_the_planner/ask.py "Which site has the most shortfall hours?"

Options: --db to point at another database file, --no-glossary to switch the glossary off.
The database is opened read only. Answers come from the planner's modeled 2011 network database, not
from the 2023 decision answer in DECISION_ANSWER.md.
"""
import argparse
import asyncio
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from planner_agent import DEFAULT_DB, ask, build_planner
from readonly_sql import connect_read_only


def has_planning_results(database):
    connection = connect_read_only(database)
    try:
        return connection.execute('SELECT COUNT(*) FROM planning_runs').fetchone()[0] > 0
    finally:
        connection.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('question')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--no-glossary', action='store_true')
    args = parser.parse_args()
    if not has_planning_results(args.db):
        print('Note: this database has no planning results yet, so questions about staffing, shortfall or cost will come back '
              'empty. Run python3 scripts/run_planning_engine.py first, or use --db ask_the_planner/eval_db/planner_for_eval.db.\n')
    planner = build_planner(args.db, use_glossary=not args.no_glossary)
    result = await ask(planner, args.question)
    for q in result['queries']:
        print('SQL:', q['sql'])
        if q['error']:
            print('  error:', q['error'])
        elif q['result'] is not None:
            print(q['result'].head(10).to_string(index=False))
        print()
    print('Answer:', result['answer'] or result['error'])


if __name__ == '__main__':
    asyncio.run(main())
