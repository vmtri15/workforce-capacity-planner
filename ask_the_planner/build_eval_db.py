"""Build the evaluation database: a copy of the planner database with the planning engine run on it.

The copy lives in ask_the_planner/eval_db/ (gitignored). The real data/workforce_planner.db is only read.
Run from the project root:
    .venv/bin/python ask_the_planner/build_eval_db.py
"""
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.planning_engine import run_planning_engine

SOURCE = ROOT / 'data/workforce_planner.db'
TARGET = HERE / 'eval_db/planner_for_eval.db'
BASE_RUN = 'base_demand_base_productivity'
# The base case views, so the simplest query is already the right one (FAILURE_REVIEW.md, fix 1).
BASE_VIEWS = {'base_case_staffing': 'staffing_plans', 'base_case_capacity': 'daily_capacity_results',
              'base_case_workload': 'modeled_daily_workload', 'base_case_summary': 'planning_run_summary'}


def add_base_views(path):
    with sqlite3.connect(path) as connection:
        for view, table in BASE_VIEWS.items():
            connection.execute(f"CREATE VIEW IF NOT EXISTS {view} AS SELECT * FROM {table} WHERE run_id = '{BASE_RUN}'")


if __name__ == '__main__':
    TARGET.parent.mkdir(exist_ok=True)
    shutil.copy(SOURCE, TARGET)
    run_planning_engine(TARGET)
    add_base_views(TARGET)
    print(f'Built {TARGET}')
