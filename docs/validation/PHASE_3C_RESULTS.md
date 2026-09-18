# Phase 3C: cross-training, hiring and transfers

Status: complete for the stated prototype scope. Final verification completed
September 15, 2026: 25 tests passed and all six scenarios were regenerated.

## What changed

The network optimizer jointly chooses overtime, temporary shifts, cross-training,
fixed-term hires and transfers. Every date and site must still cover the 95%
target for both modeled processes. A sending site loses a transferred worker's
whole regular-day capacity; the receiving site gains only the time remaining
after paid round-trip travel. This prevents counting the same person twice.

Baseline inputs and the 102-person synthetic roster are retained. The scenarios
replay historical demand using current-policy research and modeled workforce
availability. No employee skills, agency quotes, candidate start dates or
facility-to-facility travel measurements have been observed.

## Research and assumptions

Research reviewed September 14, 2026:

- [DOL Fact Sheet 22](https://www.dol.gov/agencies/whd/fact-sheets/22-flsa-hours-worked) describes compensable training and travel between job sites during the workday. Training and travel therefore consume paid time in this prototype. The existing weekly overtime controls remain in force.
- [O*NET: Packers and Packagers, Hand](https://www.onetonline.org/link/details/53-7064.00) and [Stockers and Order Fillers](https://www.onetonline.org/link/summary/53-7065.00) describe the two occupational workflows. These are role references, not evidence that any individual is qualified to switch roles.
- [OSHA training responsibilities](https://www.osha.gov/laws-regs/standardinterpretations/2000-09-21-0) supports site/task readiness before work. Existing temporary workers retain their Phase 3B readiness gate; new hire training is modeled explicitly here.

These sources support the constraint design. They do not establish the numerical
parameters below. Those are editable synthetic sensitivities in
`config/workforce_actions.json`.

| Action | Initial modeled controls | Cost/time accounting |
| --- | --- | --- |
| Cross-training | First two synthetic packers per site eligible; four paid training hours on their first scheduled day; picking eligibility starts later | Packing capacity decreases during training. A $100 external-trainer fee is incremental; regular wages are already in the baseline. |
| Cross-role work | Up to four paid hours per eligible scheduled day; 75% of incumbent picking productivity | Packing loses those hours and must still meet its target. Picking gains reduced effective capacity. The worker stays at the same site. |
| Fixed-term hiring | Three candidate slots per site; 14-calendar-day recruitment lead; two paid training days; Monday–Friday work; 80% productivity afterward | $600 recruiting/external-training fee plus every scheduled paid day through the horizon, including training and quiet days. No production during training. |
| Transfers | First two synthetic pickers per site eligible; six directed routes; destination readiness after three days | Whole-day transfer removes origin capacity. Two paid travel hours reduce destination work; $25 transport cost is incremental. No origin overtime on a transfer day. |
| Slower-travel sensitivity | Four round-trip paid travel hours | Re-solves the low-productivity case with less destination capacity. |

The first-worker selection is a reproducible synthetic eligibility rule, not a
real personnel recommendation. External trainer fees assume an available
provider; internal trainer workload is not modeled. Fixed-term employment ends
at the modeled horizon for costing, with no post-horizon commitment included.

The uniform two- and four-hour travel settings are sensitivity values, not
measured journey times between the three study areas. Facility addresses and
route-specific costs would be required before an operational transfer decision.

## Result interpretation

Verified saved results (September 15, 2026; USD incremental cost over the
56-day modeled horizon, excluding regular baseline payroll):

| Scenario | Solver status | Added cost | Cost lower bound |
| --- | --- | ---: | ---: |
| Base productivity, expanded actions | OPTIMAL | $2,189.92 | $2,189.92 |
| Low productivity, expanded actions | FEASIBLE | $26,208.46 | $26,106.11 |
| High productivity, expanded actions | OPTIMAL | $0.00 | $0.00 |
| Low productivity, four-hour transfer travel | OPTIMAL | $26,319.34 | $26,319.34 |
| Low productivity, no new actions | INFEASIBLE | — | — |
| Low productivity, delayed hiring only | INFEASIBLE | — | — |

Amounts are rounded for display; the saved JSON retains calculation precision.
The low-productivity plan uses overtime, 28 temporary shifts, six cross-training
actions, 37 cross-role worker-days, one fixed-term hire and two transfer days.
Its cost is within $102.36 of the reported lower bound, but optimality was not
proven within the 30-second solve limit. Comparing its cost to the optimal
slower-travel result does not establish an exact minimum-cost travel penalty.

The saved run is `data/processed/network_optimization_results.json`. It records
the solver status and lower cost bound alongside the chosen action plan. An
OPTIMAL result is optimal only within this fixed roster, candidate pool, policy,
action menu and historical workload. FEASIBLE means the chosen plan meets the
modeled constraints but the solver has not proven minimum cost. It must not be
presented as an optimal savings estimate.

The base case can improve on the Phase 3B cost by training selected packers and
using their available time on peak picking days. The constrained low case can
become feasible when the new actions are enabled. Delaying hiring beyond the
horizon with training and transfers disabled does not restore feasibility.

Each action is dated and tied to a synthetic worker or candidate. The output
includes training/production dates, readiness, origin/destination, paid hours,
incremental cost, reconstructed daily capacity and eligibility records.

## Validation

The final run used OR-Tools 9.15.6755, matching `requirements.txt`, in the
temporary local environment `/tmp/workforce-planner-runtime.VPVfxs` after cloud
placeholders were downloaded. The commands below are the normal project setup;
the temporary runtime is not a project dependency.

All 25 tests passed: 13 network-action tests and 12 existing optimization/roster
tests. Added regression cases reject an unpaid quiet day in a guaranteed hire
schedule, missing hire eligibility, duplicate hire actions, and hiring schedules
that exceed the configured weekly policy.

All four feasible/optimal saved plans passed the decoder audit and each contains
336 passing daily site-role target checks (56 days × three sites × two roles).
The two infeasible cases contain neither a cost nor selected actions. Saved
implementation and database hashes were checked against the current files.

The test suite includes known-cost examples for training, hiring and transfers,
plus failure cases for same-day use before training, packing shortages after
redeployment, donor shortages, longer travel, late hiring and a worker being
sent to two sites simultaneously. Existing roster and weekly-limit tests remain
part of the suite.

After each solve, a separate action decoder reconstructs capacity and costs,
checks training/readiness, paid hiring schedules, weekly overtime, temporary
worker days off and duplicate actions. Both origin and destination targets are
checked after transfers. Infeasible/unknown results return no total cost.

The database is read-only. The output saves database and implementation hashes,
policy snapshots and the solver version. The 30-second solver limit can produce
different FEASIBLE plans on different machines; the exact saved plan is auditable
but a time-limited incumbent is not guaranteed to repeat byte for byte.

```bash
.venv/bin/python scripts/run_network_optimization.py
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

## Remaining boundary and next step

This remains daily picking/packing capacity analysis. Meeting both separate
targets does not establish end-to-end shipment service or intraday coverage.
Packing capacity is protected by daily workload constraints; actual packer
availability within each shift must be checked before cross-role assignments.
Recruitment and training parameters, skill eligibility and travel must be
calibrated before use with a real workforce.

Next, carry unfinished work into subsequent days and introduce dated absences.
That will test whether an apparent daily solution creates a growing backlog,
misses an age limit, or depends on workers who are unavailable. Phase 3C does
not yet implement that queue or absence-replacement logic.
