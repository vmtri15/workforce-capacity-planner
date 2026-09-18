"""Deterministic Phase 2B workforce capacity planning engine."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class EngineInputs:
    source_window_start: str
    source_window_end: str
    demand_scale: float
    paid_hours: float
    shifts_per_day: int
    productive_time_factor: float
    service_target: float
    packages_per_order: float


PRODUCTIVITY_CASES = {
    "low": {"fulfillment_associate": "pick_rate_low", "packing_associate": "pack_rate_low"},
    "base": {"fulfillment_associate": "pick_rate_base", "packing_associate": "pack_rate_base"},
    "high": {"fulfillment_associate": "pick_rate_high", "packing_associate": "pack_rate_high"},
}


def assumption_map(connection: sqlite3.Connection) -> dict[str, float | str]:
    rows = connection.execute(
        "SELECT assumption_key, numeric_value, text_value FROM scenario_assumptions"
    ).fetchall()
    return {key: numeric if numeric is not None else text for key, numeric, text in rows}


def load_inputs(connection: sqlite3.Connection) -> EngineInputs:
    values = assumption_map(connection)
    return EngineInputs(
        source_window_start=str(values["source_window_start"]),
        source_window_end=str(values["source_window_end"]),
        demand_scale=float(values["demand_scale"]),
        paid_hours=float(values["paid_hours_per_shift"]),
        shifts_per_day=int(values["shifts_per_day"]),
        productive_time_factor=float(values["productive_time_factor"]),
        service_target=float(values["service_target"]),
        packages_per_order=float(values["packages_per_order"]),
    )


def percentile_nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def build_calendar_workload(
    observed_rows: list[sqlite3.Row], start: str, end: str
) -> list[dict[str, int | str | None]]:
    """Return every calendar date in the window, using zero for absent source dates."""
    observed = {row["source_date"]: row for row in observed_rows}
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    rows: list[dict[str, int | str | None]] = []
    while current <= final:
        planning_date = current.isoformat()
        source = observed.get(planning_date)
        rows.append(
            {
                "planning_date": planning_date,
                "source_date": planning_date if source is not None else None,
                "source_record_present": int(source is not None),
                "distinct_invoice_ids": int(source["distinct_invoice_ids"]) if source is not None else 0,
                "positive_quantity_lines": int(source["positive_quantity_lines"]) if source is not None else 0,
                "positive_units": int(source["positive_units"]) if source is not None else 0,
            }
        )
        current += timedelta(days=1)
    return rows


def allocate_integer(total: int, shares: list[tuple[str, float]]) -> dict[str, int]:
    raw = [(site_id, total * share) for site_id, share in shares]
    result = {site_id: math.floor(value) for site_id, value in raw}
    remaining = total - sum(result.values())
    ranked = sorted(raw, key=lambda item: (-(item[1] - math.floor(item[1])), item[0]))
    for site_id, _ in ranked[:remaining]:
        result[site_id] += 1
    return result


def wage_area_for_site(site_id: str) -> str:
    return "Kenosha, WI" if site_id == "kenosha" else "Chicago-Naperville-Elgin, IL-IN"


def build_base_staffing(
    connection: sqlite3.Connection,
    inputs: EngineInputs,
    workload: list[dict[str, int | str | None]],
    shares: list[tuple[str, float]],
) -> dict[tuple[str, str], int]:
    assumptions = assumption_map(connection)
    scaled_lines = [round(row["positive_quantity_lines"] * inputs.demand_scale) for row in workload]
    scaled_orders = [round(row["distinct_invoice_ids"] * inputs.demand_scale) for row in workload]
    line_p95 = percentile_nearest_rank(scaled_lines, 0.95)
    order_p95 = percentile_nearest_rank(scaled_orders, 0.95)
    productive_hours = inputs.paid_hours * inputs.productive_time_factor
    base_pick_rate = float(assumptions["pick_rate_base"])
    base_pack_rate = float(assumptions["pack_rate_base"])
    plan: dict[tuple[str, str], int] = {}
    for site_id, share in shares:
        plan[(site_id, "fulfillment_associate")] = math.ceil(line_p95 * share / (base_pick_rate * productive_hours))
        calculated_packers = math.ceil(order_p95 * inputs.packages_per_order * share / (base_pack_rate * productive_hours))
        plan[(site_id, "packing_associate")] = max(inputs.shifts_per_day, calculated_packers)
        plan[(site_id, "warehouse_supervisor")] = inputs.shifts_per_day
        plan[(site_id, "shipping_receiving_coordinator")] = 1
    return plan


def insert_run(
    connection: sqlite3.Connection,
    run_id: str,
    productivity_case: str,
    inputs: EngineInputs,
) -> None:
    connection.execute("DELETE FROM planning_runs WHERE run_id = ?", (run_id,))
    connection.execute(
        "INSERT INTO planning_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            f"Base demand / {productivity_case} productivity",
            productivity_case,
            inputs.source_window_start,
            inputs.source_window_end,
            inputs.demand_scale,
            inputs.service_target,
            "Fixed staffing calculated from base-rate capacity at the 95th percentile of daily workload",
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def insert_staffing_plan(
    connection: sqlite3.Connection,
    run_id: str,
    plan: dict[tuple[str, str], int],
    inputs: EngineInputs,
) -> None:
    rows = []
    for (site_id, role_id), headcount in plan.items():
        area = wage_area_for_site(site_id)
        wage = connection.execute(
            "SELECT median_hourly_wage FROM wage_benchmarks WHERE benchmark_area = ? AND role_id = ?",
            (area, role_id),
        ).fetchone()[0]
        rule = {
            "fulfillment_associate": "Base-rate capacity at 95th percentile daily lines",
            "packing_associate": "Base-rate capacity at 95th percentile daily orders; minimum one per shift",
            "warehouse_supervisor": "One supervisor per shift",
            "shipping_receiving_coordinator": "One coordinator per operating day",
        }[role_id]
        rows.append((run_id, site_id, role_id, headcount, inputs.paid_hours, wage, rule))
    connection.executemany("INSERT INTO staffing_plans VALUES (?, ?, ?, ?, ?, ?, ?)", rows)


def run_case(
    connection: sqlite3.Connection,
    productivity_case: str,
    inputs: EngineInputs,
    workload: list[dict[str, int | str | None]],
    shares: list[tuple[str, float]],
    base_plan: dict[tuple[str, str], int],
) -> None:
    run_id = f"base_demand_{productivity_case}_productivity"
    insert_run(connection, run_id, productivity_case, inputs)
    insert_staffing_plan(connection, run_id, base_plan, inputs)
    assumptions = assumption_map(connection)
    rates = {
        role_id: float(assumptions[key])
        for role_id, key in PRODUCTIVITY_CASES[productivity_case].items()
    }
    productive_hours_per_person = inputs.paid_hours * inputs.productive_time_factor

    for source_row in workload:
        scaled = {
            "orders": round(source_row["distinct_invoice_ids"] * inputs.demand_scale),
            "lines": round(source_row["positive_quantity_lines"] * inputs.demand_scale),
            "units": round(source_row["positive_units"] * inputs.demand_scale),
        }
        allocations = {name: allocate_integer(value, shares) for name, value in scaled.items()}
        pack_total = round(scaled["orders"] * inputs.packages_per_order)
        pack_allocations = allocate_integer(pack_total, shares)

        for site_id, _ in shares:
            connection.execute(
                "INSERT INTO modeled_daily_workload VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, source_row["planning_date"], source_row["source_date"],
                    source_row["source_record_present"], site_id,
                    allocations["orders"][site_id], allocations["lines"][site_id],
                    allocations["units"][site_id], pack_allocations[site_id],
                ),
            )
            for role_id, workload_quantity in (
                ("fulfillment_associate", allocations["lines"][site_id]),
                ("packing_associate", pack_allocations[site_id]),
            ):
                rate = rates[role_id]
                headcount = base_plan[(site_id, role_id)]
                available_hours = headcount * productive_hours_per_person
                required_hours = workload_quantity / rate
                capacity_quantity = available_hours * rate
                completed = min(float(workload_quantity), capacity_quantity)
                coverage = 1.0 if workload_quantity == 0 else completed / workload_quantity
                wage = connection.execute(
                    "SELECT median_hourly_wage FROM staffing_plans WHERE run_id = ? AND site_id = ? AND role_id = ?",
                    (run_id, site_id, role_id),
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO daily_capacity_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id, source_row["planning_date"], site_id, role_id, workload_quantity,
                        rate, required_hours, headcount, available_hours, capacity_quantity,
                        completed, max(required_hours - available_hours, 0.0),
                        max(available_hours - required_hours, 0.0), coverage,
                        int(coverage >= inputs.service_target), headcount * inputs.paid_hours * wage,
                    ),
                )


def record_quality_check(
    connection: sqlite3.Connection,
    name: str,
    passed: bool,
    observed: object,
    expected: object,
) -> None:
    connection.execute(
        "INSERT INTO planning_quality_results VALUES (?, ?, ?, ?)",
        (name, "PASS" if passed else "FAIL", str(observed), str(expected)),
    )


def validate_results(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM planning_quality_results")
    run_count = connection.execute("SELECT COUNT(*) FROM planning_runs").fetchone()[0]
    workload_count = connection.execute("SELECT COUNT(*) FROM modeled_daily_workload").fetchone()[0]
    capacity_count = connection.execute("SELECT COUNT(*) FROM daily_capacity_results").fetchone()[0]
    staffing_count = connection.execute("SELECT COUNT(*) FROM staffing_plans").fetchone()[0]
    missing_dates = connection.execute(
        "SELECT COUNT(DISTINCT planning_date) FROM modeled_daily_workload WHERE source_record_present = 0"
    ).fetchone()[0]
    record_quality_check(connection, "three_planning_runs", run_count == 3, run_count, 3)
    record_quality_check(connection, "full_calendar_workload_rows", workload_count == 504, workload_count, 504)
    record_quality_check(connection, "direct_role_capacity_rows", capacity_count == 1008, capacity_count, 1008)
    record_quality_check(connection, "fixed_staffing_rows", staffing_count == 36, staffing_count, 36)
    record_quality_check(connection, "explicit_zero_source_dates", missing_dates == 8, missing_dates, 8)

    headcount_variants = connection.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT site_id, role_id
            FROM staffing_plans
            GROUP BY site_id, role_id
            HAVING COUNT(DISTINCT scheduled_headcount) > 1
        )
        """
    ).fetchone()[0]
    record_quality_check(connection, "staffing_identical_across_cases", headcount_variants == 0, headcount_variants, 0)

    allocation_errors = connection.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT m.run_id, m.planning_date
            FROM modeled_daily_workload m
            LEFT JOIN workload_daily_source w ON w.source_date = m.source_date
            JOIN planning_runs r ON r.run_id = m.run_id
            GROUP BY m.run_id, m.planning_date
            HAVING SUM(m.modeled_orders) != ROUND(COALESCE(MAX(w.distinct_invoice_ids), 0) * MAX(r.demand_scale))
                OR SUM(m.modeled_order_lines) != ROUND(COALESCE(MAX(w.positive_quantity_lines), 0) * MAX(r.demand_scale))
                OR SUM(m.modeled_units) != ROUND(COALESCE(MAX(w.positive_units), 0) * MAX(r.demand_scale))
        )
        """
    ).fetchone()[0]
    record_quality_check(connection, "site_allocations_preserve_totals", allocation_errors == 0, allocation_errors, 0)

    gap_hours = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT productivity_case, SUM(capacity_gap_hours) FROM daily_capacity_results JOIN planning_runs USING (run_id) GROUP BY productivity_case"
        )
    }
    monotonic = gap_hours["low"] >= gap_hours["base"] >= gap_hours["high"]
    record_quality_check(
        connection,
        "gap_hours_decline_with_productivity",
        monotonic,
        f"{gap_hours['low']:.2f}>={gap_hours['base']:.2f}>={gap_hours['high']:.2f}",
        "low>=base>=high",
    )

    failed = connection.execute(
        "SELECT check_name FROM planning_quality_results WHERE status = 'FAIL'"
    ).fetchall()
    if failed:
        raise RuntimeError("Planning quality checks failed: " + ", ".join(row[0] for row in failed))


def run_planning_engine(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        inputs = load_inputs(connection)
        observed_workload = connection.execute(
            """
            SELECT * FROM workload_daily_source
            WHERE source_date BETWEEN ? AND ?
            ORDER BY source_date
            """,
            (inputs.source_window_start, inputs.source_window_end),
        ).fetchall()
        workload = build_calendar_workload(
            observed_workload, inputs.source_window_start, inputs.source_window_end
        )
        shares = [tuple(row) for row in connection.execute("SELECT site_id, allocation_share FROM sites ORDER BY site_id")]
        if len(observed_workload) != 48 or len(workload) != 56:
            raise RuntimeError(
                f"Expected 48 observed source days and 56 calendar days; found {len(observed_workload)} and {len(workload)}"
            )
        base_plan = build_base_staffing(connection, inputs, workload, shares)
        for productivity_case in PRODUCTIVITY_CASES:
            run_case(connection, productivity_case, inputs, workload, shares, base_plan)
        validate_results(connection)
        connection.commit()
    finally:
        connection.close()
