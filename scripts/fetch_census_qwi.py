"""Fetch reproducible county-level QWI labor-flow context for NAICS 493."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data/raw/census/qwi"
START_QUARTER = "2021-Q1"
# A future upper bound lets the API return every currently published quarter
# without silently freezing the extract at an older release.
REQUEST_END_QUARTER = "2026-Q4"
OUTPUT = PROJECT_ROOT / "data/processed/qwi_2021q1_latest_naics493.csv"
COUNTIES = {
    ("17", "031"): "Cook County, Illinois",
    ("17", "043"): "DuPage County, Illinois",
    ("17", "197"): "Will County, Illinois",
    ("55", "059"): "Kenosha County, Wisconsin",
}


def load_api_key() -> str:
    if os.environ.get("CENSUS_API_KEY"):
        return os.environ["CENSUS_API_KEY"]
    env_file = PROJECT_ROOT / ".env"
    for line in env_file.read_text().splitlines():
        if line.startswith("CENSUS_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("CENSUS_API_KEY is missing from the environment and .env")


def fetch_county(state: str, county: str, api_key: str) -> list[list[str]]:
    parameters = {
        "get": "Emp,EmpEnd,Sep,HirA,EmpS",
        "for": f"county:{county}",
        "in": f"state:{state}",
        "time": f"from {START_QUARTER} to {REQUEST_END_QUARTER}",
        "industry": "493",
        "sex": "0",
        "agegrp": "A00",
        "key": api_key,
    }
    url = "https://api.census.gov/data/timeseries/qwi/sa?" + urlencode(parameters)
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def main() -> None:
    api_key = load_api_key()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output_rows = []

    for (state, county), geography_name in COUNTIES.items():
        payload = fetch_county(state, county, api_key)
        raw_path = RAW_DIR / f"qwi_{state}_{county}_493_2021q1_latest.json"
        raw_path.write_text(json.dumps(payload, indent=2) + "\n")
        header = payload[0]
        for values in payload[1:]:
            record = dict(zip(header, values))
            output_rows.append(
                {
                    "geography_name": geography_name,
                    "state_fips": record["state"],
                    "county_fips": record["county"],
                    "quarter": record["time"],
                    "naics_code": record["industry"],
                    "beginning_employment": record["Emp"],
                    "end_employment": record["EmpEnd"],
                    "separations": record["Sep"],
                    "hires": record["HirA"],
                    "stable_employment": record["EmpS"],
                }
            )

    output_rows.sort(key=lambda row: (row["state_fips"], row["county_fips"], row["quarter"]))
    with OUTPUT.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    quarters = sorted({row["quarter"] for row in output_rows})
    print(f"Wrote {len(output_rows)} QWI rows ({quarters[0]} to {quarters[-1]}) to {OUTPUT}")


if __name__ == "__main__":
    main()
