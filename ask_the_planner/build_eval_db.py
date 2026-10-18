"""Build the evaluation database: a copy of the planner database with the planning engine run on it.

The copy lives in ask_the_planner/eval_db/ (gitignored). The real data/workforce_planner.db is only read.
Run from the project root:
    .venv/bin/python ask_the_planner/build_eval_db.py
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'src'))
from workforce_planner.planning_engine import run_planning_engine

SOURCE = ROOT / 'data/workforce_planner.db'
TARGET = HERE / 'eval_db/planner_for_eval.db'

if __name__ == '__main__':
    TARGET.parent.mkdir(exist_ok=True)
    shutil.copy(SOURCE, TARGET)
    run_planning_engine(TARGET)
    print(f'Built {TARGET}')
