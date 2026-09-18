"""Extract the four model-role wage benchmarks from saved BLS OEWS JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data/raw/bls/oews_2025"
OUTPUT = PROJECT_ROOT / "data/processed/oews_2025_role_wage_benchmarks.csv"
ROLE_BY_SOC = {
    "53-7065": "Fulfillment associate",
    "53-7064": "Packing associate",
    "43-5071": "Shipping and receiving coordinator",
    "53-1047": "Warehouse supervisor",
}
AREA_FILES = {
    "Chicago-Naperville-Elgin, IL-IN": RAW_DIR / "chicago_16980.json",
    "Kenosha, WI": RAW_DIR / "kenosha_28450.json",
}
METRICS = {"01": "employment", "03": "mean_hourly_wage", "08": "median_hourly_wage"}


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = []
    for area, source_file in AREA_FILES.items():
        records = json.loads(source_file.read_text())
        grouped: dict[str, dict[str, str]] = {}
        for record in records:
            code = record["formattedOccupationCode"]
            if code not in ROLE_BY_SOC or record["datatypeCode"] not in METRICS:
                continue
            row = grouped.setdefault(code, {"occupation_title": record["occupationName"]})
            row[METRICS[record["datatypeCode"]]] = record["value"].strip()
        for code, metrics in grouped.items():
            result.append(
                {
                    "release": "May 2025 OEWS",
                    "benchmark_area": area,
                    "planning_role": ROLE_BY_SOC[code],
                    "soc_code": code,
                    **metrics,
                    "source_file": str(source_file.relative_to(PROJECT_ROOT)),
                }
            )
    with OUTPUT.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    print(f"Wrote {len(result)} wage benchmark rows to {OUTPUT}")


if __name__ == "__main__":
    main()
