"""Run the Phase 2B capacity engine against the generated SQLite database."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from workforce_planner.planning_engine import run_planning_engine


if __name__ == "__main__":
    database_path = PROJECT_ROOT / "data/workforce_planner.db"
    run_planning_engine(database_path)
    print(f"Completed planning runs in {database_path}")
