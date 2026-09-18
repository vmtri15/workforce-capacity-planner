# Phase 3B: constrained staffing optimization

## Decision and evidence boundary

The optimizer chooses additional overtime hours and temporary shifts to meet
each site's picking and packing target at minimum incremental modeled cost,
conditional on a fixed synthetic regular roster. OR-Tools CP-SAT implements
integer decisions and returns its actual solver status. Groups are independent
because this increment does not transfer workers or share a cross-trained pool.

The exercise replays historical demand with current-policy research; it is not
a reconstruction of 2011 employment practices. No real employee roster, agency
availability, individual consent or training records were supplied. The roster,
availability, action caps and readiness dates are explicitly synthetic.

## Research informing constraints

Reviewed September 13, 2026:

- [DOL Fact Sheet 23](https://www.dol.gov/agencies/whd/fact-sheets/23-flsa-overtime-pay) establishes the general federal overtime trigger after 40 hours in a recurring workweek for covered nonexempt employees. The prototype uses Monday–Sunday, limits regular scheduled time to at most 40 hours and conservatively prices every additional hour at 1.5x the wage proxy. This is not individual payroll calculation. Daily/weekly overtime caps are employer-policy assumptions.
- [Illinois ODRISA guidance](https://labor.illinois.gov/laws-rules/fls/odrisa.html) describes rest within consecutive seven-day windows, with exceptions and meal-period requirements. [Wisconsin DWD guidance](https://dwd.wisconsin.gov/er/laborstandards/restday.htm) describes calendar-week rest for covered factory/retail establishments. Applicability to a modeled facility is not established here. Five workdays per rolling seven is a uniform prototype policy. Daily assignments do not verify meal timing, shift handoffs or continuous rest hours.
- [OSHA temporary-worker training interpretation](https://www.osha.gov/laws-regs/standardinterpretations/2000-09-21-0) supports requiring task/site readiness before assigning capacity. No official source supplies this project's onboarding duration or available pool size.
- [DOL hours-worked guidance](https://www.dol.gov/agencies/whd/fact-sheets/22-flsa-hours-worked) describes when training counts as paid work. This increment gates temporary availability by an assumed readiness date; it does not schedule or cost training. Temporary workers are assumed to have completed applicable preparation externally by that date. A future training action must include paid nonproductive time and costs.
- [Google's employee scheduling documentation](https://developers.google.com/optimization/scheduling/employee_scheduling) provides the official CP-SAT scheduling approach. Local package version: OR-Tools 9.15.6755.

## Roster and policy

The minimum repeating roster has **102 synthetic people**: 41 at Joliet, 41 at
O'Hare and 20 at Kenosha. It covers exactly 69 active positions each day and
3,864 paid-day assignments across the 56-day window. Each site-role roster is
sized at `ceil(7 * daily_positions / 5)`. Some employees work fewer than five
days; no additional guaranteed-hours payment is modeled. All four roles retain
their baseline daily coverage. The optimizer adds capacity only to picking and
packing.

The seven-day template repeats before and after the modeled window. Full
regular-template hours are reserved in partial boundary weeks; additional work
outside the horizon is assumed zero. This avoids granting extra overtime merely
because the first or last workweek is incomplete in the data.

Editable inputs are in `config/optimization.json`:

| Control | Default | Classification |
| --- | --- | --- |
| Completion target | 95% for each site-role-date | Existing prototype target |
| Regular paid shift | 8 hours, read from database | Assumed |
| Productive-time factor | 85%, read from database | Assumed |
| Regular days | At most 5 per rolling 7 days | Policy assumption |
| Additional hours | 15-minute blocks, at most 2 per scheduled worker-day | Policy assumption |
| Weekly additional hours | At most 8 per person | Policy assumption |
| Total weekly hours | At most 48 including regular hours | Policy assumption |
| Overtime availability | Scheduled regular days, excluding configured unavailable dates | Synthetic |
| Temporary pool | Six distinct people per site-direct-role | Synthetic; pools do not overlap |
| Temporary readiness | Start of horizon plus 3 calendar days | Assumed availability delay, not estimated training time |
| Temporary assignments | Whole 8-hour shifts; at most 5 per calendar and rolling 7-day week | Policy assumption |
| Temporary productivity | 80% of incumbent rate after readiness | Uncalibrated sensitivity |
| Additional wage / temp bill rate | 1.5x OEWS median wage proxy | Cost assumption; not an agency quote |

Dates blocked in the configuration apply to the corresponding action pool.
Baseline attendance remains assumed; absence replacement is future work. Worker
IDs, assigned dates, additional hours and action costs are saved for audit.

## Verified results

| Scenario | Solver status | Incremental cost | Interpretation |
| --- | --- | ---: | --- |
| Base productivity | OPTIMAL | $2,421.73 | 84.5 paid overtime hours, zero temporary shifts |
| Low productivity | INFEASIBLE | No valid total | Available overtime and finite temp pools cannot cover all target demand |
| High productivity | OPTIMAL | $0.00 | Existing capacity covers the target |
| Overtime unavailable | OPTIMAL | $3,679.56 | 16 temporary shifts cover the base target |
| No overtime, temp readiness after horizon | INFEASIBLE | No valid total | Capacity unavailable before peak needs |
| Low productivity, 1-hour weekly OT cap, no temp pool | INFEASIBLE | No valid total | Restricted actions cannot cover the target |

At low productivity, even ignoring weekly competition for labor, the maximum
daily additions leave 562.75 target order lines uncovered at Joliet and 311.00 at
O'Hare on December 5. These are upper-bound capacity diagnostics; a feasible
schedule cannot improve on that upper bound without changing a constraint.

The base cost exceeds Phase 3A's $2,391.56 by $30.17 because work is now purchased
in 15-minute blocks. Optimality applies to these two actions with the fixed
roster and policy. It does not establish an optimum across hiring, training,
transfers, alternative regular rosters or all possible labor arrangements.

Costs are incremental wage/bill-rate proxies above existing baseline spending.
They exclude benefit loading, external onboarding costs, guaranteed-hours
payments and travel. Service is measured separately for each daily process;
this is not end-to-end shipment completion. Unfinished demand does not carry
forward yet, and within-day shift coverage is not modeled.

## Validation and reproducibility

Twelve unit tests cover exact regular coverage and minimum roster sizing,
rolling days off, determinism, invalid inputs, an independently calculable
mixed-action optimum, weekly caps, readiness, unavailable dates, boundary-week
hours, zero shortages and cross-week temporary-worker rest.

Every feasible decoded solution is checked again for action availability,
daily/weekly caps, roster membership, temporary readiness, distinct pool size,
rolling days off and achievement of the daily target. Feasible group results
inside an infeasible overall scenario are partial diagnostics only. No overall
cost is returned for an infeasible or unknown scenario. Time-limited feasible
solutions remain labeled FEASIBLE, not OPTIMAL, with group lower cost bounds.

`data/processed/optimization_results.json` includes the roster, policies, group
statuses, actions, daily coverage, solver version and database SHA-256. The
database is read-only during optimization. Results replace the previous JSON
only after solving and checking the full scenario set.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3 scripts/build_database.py
python3 scripts/run_planning_engine.py
.venv/bin/python scripts/run_optimization.py
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

## Next increment

Phase 3B is complete for finite-pool overtime and temporary shifts. Phase 3
remains open: add paid training and cross-role eligibility, hiring readiness,
transfer travel time and donor coverage, then backlog and absence stress tests.
These constraints must be explicit before broadening recommendations.
