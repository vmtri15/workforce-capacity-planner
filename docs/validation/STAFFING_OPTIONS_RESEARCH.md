# Phase 3A: staffing options and preliminary comparison

## Research basis

Reviewed September 13, 2026.

- [U.S. Department of Labor, Fact Sheet 23](https://www.dol.gov/agencies/whd/fact-sheets/23-flsa-overtime-pay): covered nonexempt employees generally receive at least 1.5 times their regular rate after 40 hours in a workweek. The comparison prices every additional hour at 1.5 times the OEWS wage proxy. This is a scenario convention, not a payroll calculation: the project has active daily positions, not employee schedules or regular-rate records.
- [OSHA, Protecting Temporary Workers](https://www.osha.gov/temporaryworkers): staffing agencies and host employers share responsibilities for protecting temporary workers. Availability cannot be treated as sufficient without suitable training and assignment readiness.
- [OSHA, Training obligations](https://www.osha.gov/laws-regs/standardinterpretations/2000-09-21-0): workplace-specific training is generally provided by the host, with the agency responsible for ensuring proper training. The model therefore treats temporary capacity as available only for a hypothetical already-onboarded pool.

Public sources establish constraints, but do not establish this project's agency
bill rate, available workers, hiring lead time, cross-training duration, or
transfer feasibility. Those inputs remain assumptions or unresolved requirements.

## Implemented comparison

`scripts/compare_staffing_options.py` reads the existing database without changing
it and saves 24 comparisons: three productivity cases, two completion targets,
and four options. Each result includes its date-site-role actions and costs.

| Option | Prototype calculation | Limitation |
| --- | --- | --- |
| No action | Retain baseline capacity | Residual shortage remains visible |
| Overtime | Fractional additional paid hours; maximum 2 per active person per day; 85% productive; 1.5x wage | Daily cap is a policy assumption; no worker-level weekly schedule or availability yet |
| Temporary shifts | Whole 8-hour shifts; 85% productive time; 80% of incumbent productivity; 1.5x wage bill-rate proxy | All three parameters are uncalibrated assumptions; assumes an available, already-trained pool with no quantity limit |
| Extra daily positions | Whole extra positions sized for the largest gap, paid every day of the 56-day window | Assumes readiness before the window; excludes hiring, training, benefits and roster coverage costs |

The script currently uses fixed 85% productive time and eight-hour shift controls
matching the baseline. These and the action controls must become configuration
inputs before editable scenario optimization. Costs are incremental above the
baseline. Existing costs cancel in this comparison; they are not a payroll budget.

## Base productivity results

| Completion target | Gap in productive hours | Overtime | Temporary shifts | Extra daily positions |
| --- | ---: | ---: | ---: | ---: |
| 95% | 70.96 | $2,391.56 | $3,679.56 | $77,781.76 |
| 100% | 113.35 | $3,814.85 | $5,763.00 | $102,618.88 |

Each action option closes its target gap in the base case under its stated
assumptions. Overtime is cheapest among these single-action comparisons. This
does not establish the best feasible mixed plan; rates, availability, weekly
schedules and onboarding may change the ranking.

The earlier Phase 2B gap of 113.35 hours measures full-demand shortage. The
service-target gap is `max(0, target * required_hours - available_hours)`, which
is 70.96 hours at 95%. Neither calculation carries backlog forward. A 95% target
allows unfinished work, and a later backlog model must account for it.

## Remaining Phase 3 work

1. Introduce configuration, weekly roster coverage, availability and onboarding constraints.
2. Represent cross-training with verified skill eligibility, training time and donor-role coverage; packing surplus alone does not establish eligible picker capacity.
3. Represent transfers only with donor-site surplus, travel time, cost and availability. Synchronized demand does not guarantee transferable capacity.
4. Model hiring readiness and roster size separately from extra daily positions.
5. Add OR-Tools for mixed actions, then compare results with these simple baselines and sensitivity cases.

Phase 3A is a preliminary benchmark. Phase 3 optimization remains in progress.
