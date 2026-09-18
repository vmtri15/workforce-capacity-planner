"""Combine daily UCI profiles after the confirmed December 2010 exact-row overlap."""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIRST = PROJECT_ROOT / "data/processed/uci_daily_2009_2010.csv"
SECOND = PROJECT_ROOT / "data/processed/uci_daily_2010_2011.csv"
OUTPUT = PROJECT_ROOT / "data/processed/uci_daily_workload_profile.csv"
OVERLAP_END = "2010-12-09"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open() as source:
        return list(csv.DictReader(source))


def main() -> None:
    first_rows = read_rows(FIRST)
    second_rows = [row for row in read_rows(SECOND) if row["planning_date"] > OVERLAP_END]
    rows = sorted(first_rows + second_rows, key=lambda row: row["planning_date"])

    with OUTPUT.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} deduplicated daily source rows to {OUTPUT}")


if __name__ == "__main__":
    main()
