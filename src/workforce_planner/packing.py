"""Basic productive packing workload, with caller-supplied scenario assumptions."""
from math import isfinite, ceil


def estimated_packing_jobs(units, assumed_units_per_job):
    """Per-order unit-count proxy; not dimension-aware cartonization."""
    if not isfinite(units) or units < 0 or not isfinite(assumed_units_per_job) or assumed_units_per_job <= 0:
        raise ValueError("Units must be nonnegative and assumed job size positive and finite")
    return ceil(units / assumed_units_per_job)


def packing_hours(packages, units, fixed_seconds, seconds_per_unit, support_seconds=0):
    values = (packages, units, fixed_seconds, seconds_per_unit, support_seconds)
    if any(not isfinite(v) or v < 0 for v in values):
        raise ValueError("Packing counts and task times must be finite and nonnegative")
    if units > 0 and packages == 0:
        raise ValueError("Positive outbound units require a positive package estimate")
    return (packages * fixed_seconds + units * seconds_per_unit + support_seconds) / 3600
