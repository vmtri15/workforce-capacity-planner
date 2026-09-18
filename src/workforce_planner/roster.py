"""Synthetic repeating weekly rosters for the daily capacity prototype.

Each site/role has the same active headcount on every calendar day. These
assignments describe paid days only: they do not establish shift start times,
employee consent, attendance, or compliance with rules concerning rest hours.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from urllib.parse import quote

from ortools.sat.python import cp_model


def _validate_inputs(
    staffing: list[dict], dates: list[str], paid_hours: float, max_days: int
) -> tuple[list[dict], list[date]]:
    if isinstance(max_days, bool) or not isinstance(max_days, int) or not 1 <= max_days <= 7:
        raise ValueError("max_days must be an integer between 1 and 7")
    if isinstance(paid_hours, bool) or not isinstance(paid_hours, (int, float)):
        raise ValueError("paid_hours must be a positive finite number")
    if not math.isfinite(paid_hours) or paid_hours <= 0:
        raise ValueError("paid_hours must be a positive finite number")
    if not isinstance(dates, list) or not dates:
        raise ValueError("dates must be a nonempty list of consecutive ISO dates")
    parsed: list[date] = []
    for value in dates:
        try:
            current = date.fromisoformat(value)
        except (TypeError, ValueError) as error:
            raise ValueError("dates must contain ISO dates in YYYY-MM-DD format") from error
        if current.isoformat() != value:
            raise ValueError("dates must contain ISO dates in YYYY-MM-DD format")
        if parsed and current != parsed[-1] + timedelta(days=1):
            raise ValueError("dates must be unique, consecutive, and in increasing order")
        parsed.append(current)
    if not isinstance(staffing, list):
        raise ValueError("staffing must be a list of site/role dictionaries")
    seen: set[tuple[str, str]] = set()
    for group in staffing:
        if not isinstance(group, dict):
            raise ValueError("each staffing group must be a dictionary")
        for field in ("site_id", "role_id"):
            if not isinstance(group.get(field), str) or not group[field].strip():
                raise ValueError(f"{field} must be a nonempty string")
        headcount = group.get("scheduled_headcount")
        if isinstance(headcount, bool) or not isinstance(headcount, int) or headcount < 0:
            raise ValueError("scheduled_headcount must be a nonnegative integer")
        key = (group["site_id"], group["role_id"])
        if key in seen:
            raise ValueError(f"duplicate staffing group: {key}")
        seen.add(key)
    return sorted(staffing, key=lambda group: (group["site_id"], group["role_id"])), parsed


def _weekly_patterns(headcount: int, max_days: int) -> tuple[list[list[int]], str]:
    """Find the minimum roster with exact daily coverage and balanced days."""
    if headcount == 0:
        return [], "EMPTY"
    worker_count = (7 * headcount + max_days - 1) // max_days
    minimum_days = (7 * headcount) // worker_count
    maximum_days = math.ceil(7 * headcount / worker_count)
    model = cp_model.CpModel()
    work = [[model.new_bool_var(f"work_{worker}_{day}") for day in range(7)]
            for worker in range(worker_count)]
    for day in range(7):
        model.add(sum(work[worker][day] for worker in range(worker_count)) == headcount)
    pattern_codes = []
    for worker in range(worker_count):
        model.add(sum(work[worker]) >= minimum_days)
        model.add(sum(work[worker]) <= min(maximum_days, max_days))
        code = model.new_int_var(0, 127, f"pattern_{worker}")
        model.add(code == sum((1 << (6 - day)) * work[worker][day] for day in range(7)))
        pattern_codes.append(code)
    # Break interchangeable-employee symmetry; final IDs follow this ordering.
    for worker in range(worker_count - 1):
        model.add(pattern_codes[worker] >= pattern_codes[worker + 1])
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 30
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"weekly roster solver returned {solver.status_name(status)}")
    patterns = [[day for day in range(7) if solver.value(work[worker][day])]
                for worker in range(worker_count)]
    return patterns, solver.status_name(status)


def build_roster(
    staffing: list[dict], dates: list[str], paid_hours: float, max_days: int = 5
) -> dict:
    """Build synthetic workers and dated baseline assignments.

    ``weekdays`` uses Monday=0 through Sunday=6. Every worker repeats their
    weekday pattern, so any rolling seven days contain at most ``max_days``
    paid shifts. The minimum employee count is ceil(7 * active headcount /
    max_days) for each site/role. Minimum counts assume unrestricted weekday
    availability; no actual employee records are used.
    """
    groups, parsed_dates = _validate_inputs(staffing, dates, paid_hours, max_days)
    workers: list[dict] = []
    assignments: list[dict] = []
    summaries: list[dict] = []
    # Groups with equal requirements share a solved template.
    cache: dict[int, tuple[list[list[int]], str]] = {}
    for group in groups:
        site_id, role_id = group["site_id"], group["role_id"]
        headcount = group["scheduled_headcount"]
        if headcount not in cache:
            cache[headcount] = _weekly_patterns(headcount, max_days)
        patterns, solver_status = cache[headcount]
        summaries.append({
            "site_id": site_id, "role_id": role_id,
            "scheduled_headcount": headcount, "roster_headcount": len(patterns),
            "solver_status": solver_status, "synthetic": True,
        })
        for index, weekdays in enumerate(patterns, start=1):
            worker_id = f"synthetic:{quote(site_id, safe='')}:{quote(role_id, safe='')}:{index:03d}"
            worker = {
                "worker_id": worker_id, "site_id": site_id, "role_id": role_id,
                "weekdays": list(weekdays), "synthetic": True,
            }
            workers.append(worker)
            for planning_date in parsed_dates:
                if planning_date.weekday() in weekdays:
                    assignments.append({
                        "worker_id": worker_id, "site_id": site_id, "role_id": role_id,
                        "planning_date": planning_date.isoformat(), "paid_hours": float(paid_hours),
                    })
    assignments.sort(key=lambda row: (row["planning_date"], row["site_id"], row["role_id"], row["worker_id"]))
    return {
        "workers": workers, "assignments": assignments, "groups": summaries,
        "synthetic": True, "max_days_per_rolling_week": max_days,
        "availability_assumption": "Unrestricted weekday availability with a repeating weekly pattern",
        "time_resolution": "daily; no shift start or end times",
    }
