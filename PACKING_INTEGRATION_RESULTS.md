# Productive-hour packing integration

September 15, 2026: all three 12/24/48-unit sensitivities return INFEASIBLE
under unchanged staffing and action policies. Each output has null incremental
cost and no actions. These outcomes concern assumed workloads and constrained
action pools; they are not calibrated estimates of actual facility understaffing.

Validation: 50 unit tests passed, including productive-hour overrides, overtime,
temporary-worker efficiency, training donor capacity, and allocation conservation.
Browser checks cover model switching, CSV export, scenario statuses, and mobile
overflow. Validation used a temporary environment with OR-Tools 9.15.6755 because
the existing environment stalled while reading dependency files.

The network optimizer accepts an optional `productive_demand_hours` field on
each daily input. Legacy quantity/rate demand remains supported. Paid shifts,
overtime, temporary workers, training losses, hiring and transfers all contribute
productive hours under the existing availability and efficiency assumptions.
The service target is applied to demand hours; no allowance is added to demand.

`scripts/run_packing_optimization.py` runs the three reviewed packing sensitivities
with the original staffing, action policies and base picking demand. Picking
still uses the older source transformation; this is a packing-only extension,
not a complete replacement of outbound demand cleaning.

Network packing hours are allocated using configured site employment shares.
This assumes the same packing mix across sites. Daily totals are preserved to
six decimal places in hours; the final site receives the rounding remainder.
There is no preferred or calibrated packing-job size among 12, 24 and 48 units.
The saved diagnostic configuration's `optimizer_integration: false` describes
the original diagnostic artifact; this separate opt-in runner performs integration.

The new results are saved separately, with input hashes and scenario evidence
labels. The dashboard shows baseline capacity for the selected workload model
and saved solver outcomes in Scenario comparison. An infeasible result has no
action recommendation or total cost. It does not establish staffing needs outside
the available action set: hiring and transfers currently support picking only.

Unresolved readiness gaps remain: measured task times, actual staffing and
availability, recruiting pipeline observations, dated absences, backlog carryover,
and validated future demand forecasts. This integration does not close those gaps.
