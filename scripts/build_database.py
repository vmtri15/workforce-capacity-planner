"""Build the reproducible SQLite data foundation from saved project inputs."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = PROJECT_ROOT / "sql/schema.sql"
OUTPUT_FILE = PROJECT_ROOT / "data/workforce_planner.db"

ROLE_ID_BY_NAME = {
    "Fulfillment associate": "fulfillment_associate",
    "Packing associate": "packing_associate",
    "Shipping and receiving coordinator": "shipping_receiving_coordinator",
    "Warehouse supervisor": "warehouse_supervisor",
}


def insert_sources(connection: sqlite3.Connection) -> None:
    rows = [
        (
            "uci_online_retail_ii",
            "Online Retail II",
            "UCI Machine Learning Repository",
            "2009-12-01 to 2011-12-09",
            "download",
            "data/raw/uci/online_retail_II.xlsx",
            "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
            "observed",
            "Historical UK retailer transactions; used only to shape modeled demand.",
        ),
        (
            "bls_oews_2025",
            "Occupational Employment and Wage Statistics",
            "U.S. Bureau of Labor Statistics",
            "May 2025",
            "public web service",
            "data/raw/bls/oews_2025/",
            "https://www.bls.gov/oes/2025/may/oessrcma.htm",
            "observed",
            "Area-wide occupational estimates; not facility offer rates or total labor cost.",
        ),
        (
            "census_cbp_2023",
            "County Business Patterns",
            "U.S. Census Bureau",
            "2023",
            "API",
            "data/raw/census/",
            "https://www.census.gov/data/developers/data-sets/cbp-zbp/cbp-api.html",
            "observed",
            "County-wide NAICS 493 totals; not e-commerce-only facilities.",
        ),
        (
            "bls_qcew_2025q4",
            "Quarterly Census of Employment and Wages",
            "U.S. Bureau of Labor Statistics",
            "2025 Q4",
            "download",
            "data/raw/bls/workforce-qcew-2025q4-493.csv",
            "https://data.bls.gov/cew/data/api/2025/4/industry/493.csv",
            "observed",
            "Used as a regional site-allocation proxy, not facility workload.",
        ),
        (
            "census_qwi_2021q1_latest",
            "Quarterly Workforce Indicators",
            "U.S. Census Bureau",
            "2021 Q1 to 2025 Q4",
            "API",
            "data/raw/census/qwi/",
            "https://www.census.gov/data/developers/data-sets/qwi.html",
            "observed",
            "County-level NAICS 493 labor flows; not a facility hiring pipeline or time-to-hire measure.",
        ),
    ]
    connection.executemany(
        "INSERT INTO source_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )


def insert_sites_and_roles(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT INTO sites VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("joliet", "Joliet/Elwood", "Will County", "IL", "Will County, IL", 0.43, "Rounded relative 2025 Q4 QCEW NAICS 493 employment"),
            ("ohare", "O'Hare area", "Cook and DuPage Counties", "IL", "Cook plus DuPage Counties, IL", 0.42, "Rounded relative 2025 Q4 QCEW NAICS 493 employment"),
            ("kenosha", "Kenosha/Pleasant Prairie", "Kenosha County", "WI", "Kenosha County, WI", 0.15, "Rounded relative 2025 Q4 QCEW NAICS 493 employment"),
        ],
    )
    connection.executemany(
        "INSERT INTO roles VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("fulfillment_associate", "Fulfillment associate", "53-7065", "53-7065", "order lines per productive hour", 1),
            ("packing_associate", "Packing associate", "53-7064", "53-7064", "pack jobs per productive hour", 1),
            ("shipping_receiving_coordinator", "Shipping and receiving coordinator", "43-5071", "43-5071", None, 0),
            ("warehouse_supervisor", "Warehouse supervisor", "53-1042", "53-1047", None, 0),
        ],
    )


def ingest_workload(connection: sqlite3.Connection) -> None:
    path = PROJECT_ROOT / "data/processed/uci_daily_workload_profile.csv"
    with path.open(newline="") as source:
        rows = [
            (
                row["planning_date"], row["source_sheet"], int(row["source_lines"]),
                int(row["distinct_invoice_ids"]), int(row["positive_quantity_lines"]),
                int(row["positive_units"]), int(row["nonpositive_quantity_lines"]),
                "uci_online_retail_ii",
            )
            for row in csv.DictReader(source)
        ]
    connection.executemany("INSERT INTO workload_daily_source VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)


def ingest_wages(connection: sqlite3.Connection) -> None:
    path = PROJECT_ROOT / "data/processed/oews_2025_role_wage_benchmarks.csv"
    with path.open(newline="") as source:
        rows = [
            (
                row["release"], row["benchmark_area"], ROLE_ID_BY_NAME[row["planning_role"]],
                row["occupation_title"], int(row["employment"]), float(row["mean_hourly_wage"]),
                float(row["median_hourly_wage"]), "bls_oews_2025",
            )
            for row in csv.DictReader(source)
        ]
    connection.executemany("INSERT INTO wage_benchmarks VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)


def ingest_cbp(connection: sqlite3.Connection) -> None:
    rows = []
    for path in sorted((PROJECT_ROOT / "data/raw/census").glob("cbp_2023_*_493.json")):
        payload = json.loads(path.read_text())
        header, values = payload[0], payload[1]
        record = dict(zip(header, values))
        rows.append(
            (
                2023, record["NAME"], record["state"], record["county"], "493",
                int(record["ESTAB"]), int(record["EMP"]), int(record["PAYANN"]),
                "census_cbp_2023",
            )
        )
    connection.executemany("INSERT INTO regional_industry_benchmarks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def ingest_qcew(connection: sqlite3.Connection) -> None:
    county_names = {
        "17031": "Cook County, Illinois",
        "17043": "DuPage County, Illinois",
        "17197": "Will County, Illinois",
        "55059": "Kenosha County, Wisconsin",
    }
    path = PROJECT_ROOT / "data/raw/bls/workforce-qcew-2025q4-493.csv"
    rows = []
    with path.open(newline="") as source:
        for row in csv.DictReader(source):
            area_fips = row["area_fips"]
            if (
                area_fips in county_names
                and row["own_code"] == "5"
                and row["size_code"] == "0"
                and row["industry_code"] == "493"
            ):
                rows.append(
                    (
                        int(row["year"]), int(row["qtr"]), area_fips,
                        county_names[area_fips], row["industry_code"], row["own_code"],
                        int(row["qtrly_estabs"]), int(row["month3_emplvl"]),
                        int(row["avg_wkly_wage"]), "bls_qcew_2025q4",
                    )
                )
    connection.executemany("INSERT INTO qcew_industry_benchmarks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def optional_integer(value: str) -> int | None:
    return int(value) if value not in ("", None) else None


def ingest_qwi(connection: sqlite3.Connection) -> None:
    path = PROJECT_ROOT / "data/processed/qwi_2021q1_latest_naics493.csv"
    with path.open(newline="") as source:
        rows = [
            (
                row["state_fips"].zfill(2), row["county_fips"].zfill(3), row["geography_name"],
                row["quarter"], row["naics_code"], optional_integer(row["beginning_employment"]),
                optional_integer(row["end_employment"]), optional_integer(row["separations"]),
                optional_integer(row["hires"]), optional_integer(row["stable_employment"]),
                "census_qwi_2021q1_latest",
            )
            for row in csv.DictReader(source)
        ]
    connection.executemany("INSERT INTO qwi_labor_flows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def insert_assumptions(connection: sqlite3.Connection) -> None:
    rows = [
        ("planning_horizon_days", 56, None, "calendar days", "design_decision", "Eight-week source-derived peak window"),
        ("source_window_start", None, "2011-10-14", "date", "observed_source_derived", "Highest consecutive 56-day order-line window"),
        ("source_window_end", None, "2011-12-08", "date", "observed_source_derived", "Highest consecutive 56-day order-line window"),
        ("demand_scale", 5.0, None, "multiplier", "assumed", "Portfolio-sized scenario control"),
        ("paid_hours_per_shift", 8.0, None, "hours", "assumed", "Editable operating assumption"),
        ("shifts_per_day", 2.0, None, "shifts", "assumed", "Editable operating assumption"),
        ("productive_time_factor", 0.85, None, "fraction", "assumed", "Editable operating assumption"),
        ("service_target", 0.95, None, "fraction of daily workload", "assumed", "End-of-day target"),
        ("pick_rate_low", 45.0, None, "lines per productive hour", "source_informed_uncalibrated", "Manual picking sensitivity"),
        ("pick_rate_base", 60.0, None, "lines per productive hour", "source_informed_uncalibrated", "Published single-picking case anchor"),
        ("pick_rate_high", 90.0, None, "lines per productive hour", "source_informed_uncalibrated", "Improvement sensitivity"),
        ("pack_rate_low", 35.0, None, "pack jobs per productive hour", "source_informed_uncalibrated", "Packing sensitivity"),
        ("pack_rate_base", 50.0, None, "pack jobs per productive hour", "source_informed_uncalibrated", "Reported workplace norm used as exploratory anchor"),
        ("pack_rate_high", 65.0, None, "pack jobs per productive hour", "source_informed_uncalibrated", "Packing sensitivity"),
        ("packages_per_order", 1.0, None, "pack jobs per order", "assumed", "UCI source does not contain parcel count"),
    ]
    connection.executemany("INSERT INTO scenario_assumptions VALUES (?, ?, ?, ?, ?, ?)", rows)


def record_check(connection: sqlite3.Connection, name: str, observed: object, expected: object, detail: str) -> None:
    status = "PASS" if observed == expected else "FAIL"
    connection.execute(
        "INSERT INTO data_quality_results VALUES (?, ?, ?, ?, ?)",
        (name, status, str(observed), str(expected), detail),
    )


def run_quality_checks(connection: sqlite3.Connection) -> None:
    record_check(connection, "workload_row_count", connection.execute("SELECT COUNT(*) FROM workload_daily_source").fetchone()[0], 604, "One row per deduplicated source date")
    record_check(connection, "workload_date_uniqueness", connection.execute("SELECT COUNT(DISTINCT source_date) FROM workload_daily_source").fetchone()[0], 604, "No duplicate dates")
    record_check(connection, "positive_line_total", connection.execute("SELECT SUM(positive_quantity_lines) FROM workload_daily_source").fetchone()[0], 1022291, "Matches verified cleaned profile")
    record_check(connection, "positive_unit_total", connection.execute("SELECT SUM(positive_units) FROM workload_daily_source").fetchone()[0], 11490122, "Matches verified cleaned profile")
    record_check(connection, "wage_row_count", connection.execute("SELECT COUNT(*) FROM wage_benchmarks").fetchone()[0], 8, "Four roles in two benchmark areas")
    record_check(connection, "cbp_row_count", connection.execute("SELECT COUNT(*) FROM regional_industry_benchmarks").fetchone()[0], 4, "Will, Cook, DuPage, and Kenosha Counties")
    record_check(connection, "qcew_row_count", connection.execute("SELECT COUNT(*) FROM qcew_industry_benchmarks").fetchone()[0], 4, "Private NAICS 493 records for Will, Cook, DuPage, and Kenosha Counties")
    record_check(connection, "qwi_row_count", connection.execute("SELECT COUNT(*) FROM qwi_labor_flows").fetchone()[0], 80, "Twenty quarters for four counties")
    record_check(connection, "qwi_quarter_coverage", connection.execute("SELECT COUNT(DISTINCT quarter) FROM qwi_labor_flows").fetchone()[0], 20, "2021 Q1 through 2025 Q4")
    share = connection.execute("SELECT ROUND(SUM(allocation_share), 6) FROM sites").fetchone()[0]
    record_check(connection, "site_share_total", share, 1.0, "Modeled site shares sum to 100 percent")
    fk_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
    record_check(connection, "foreign_key_integrity", len(fk_issues), 0, "All source and role references resolve")


def build_database() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix="workforce_planner_", suffix=".db", dir=OUTPUT_FILE.parent)
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            connection.executescript(SCHEMA_FILE.read_text())
            insert_sources(connection)
            insert_sites_and_roles(connection)
            ingest_workload(connection)
            ingest_wages(connection)
            ingest_cbp(connection)
            ingest_qcew(connection)
            ingest_qwi(connection)
            insert_assumptions(connection)
            run_quality_checks(connection)
            failures = connection.execute("SELECT check_name FROM data_quality_results WHERE status = 'FAIL'").fetchall()
            if failures:
                raise RuntimeError(f"Data quality checks failed: {failures}")
            connection.commit()
        finally:
            connection.close()
        os.replace(temporary_path, OUTPUT_FILE)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    print(f"Built {OUTPUT_FILE}")


if __name__ == "__main__":
    build_database()
