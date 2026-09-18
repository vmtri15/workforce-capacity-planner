# Hypothetical Service and Cost Comparison

## Scope

Thirty predeclared policies were replayed over 36 stress cases each (1,080 runs).
All use the existing FIFO service engine and a 95% unit-completion target within
two operating days. Policies combine 0-4 additional permanent workers above six,
0/2 maximum overtime hours per present worker, and 0/2/4 temporary shifts per day.
Stress cases combine 30/40/50 units per productive hour, 0/1/2 persistent absences,
one/three operating-day temporary lead times, and retained/deduplicated demand.
Lead-time variants are identical when no temporary shifts are enabled; counts
are coverage of the grid, not independent trials or probabilities.

Config: `config/staffing_cost_scenarios.json`. Illustrative rates are $22 per
regular paid hour, 1.5 times that for overtime, and $30 per temporary hour.
These are hypothetical USD scenario costs, not verified wages or agency quotes.

## Main Results

| Policy | Base unit service | Base modeled cost | Lowest service across stresses |
| --- | ---: | ---: | ---: |
| Six workers, no actions | 95.81% | $238,656 | 0.80% |
| Six, up to 2h overtime | 97.59% | $242,253 | 1.20% |
| Six, up to four temporary shifts | 98.49% | $244,896 | 9.48% |
| Six, overtime and temporary shifts | 99.02% | $245,604 | 28.65% |
| Nine, up to 2h overtime | 99.82% | $359,040 | 95.36% |
| Ten, no actions | 99.79% | $397,760 | 95.81% |

Base means retained demand, 40 units/productive hour, no absences and one-day
temporary lead time. Costs cover the entire January 5-November 16, 2023 replay,
including 28 zero-arrival recovery days; they are not monthly or annual figures.
The horizon has 226 paid operating days for each regular worker, including idle
and absent days. This paid-absence assumption affects cost interpretation.

Six workers without actions are the lowest-cost passing policy in the base case.
Nine with reactive overtime are the lowest maximum-cost policy among those that
pass every tested stress: worst-case service 95.36%, worst-case cost $365,772.
Ten without actions also pass every stress at $397,760. Neither is a proven
global optimum, an actual hiring recommendation or a measured saving.

## How Actions Work

Overtime responds to unfinished units due today or overdue, after regular and
already-booked temporary capacity. It is allocated in whole paid hours across
present workers, capped at two per present worker; productive time is applied
once. Individual worker assignments and weekly limits are not modeled.

Temporary workers are 80% as productive as regular workers and booked for full
eight-hour shifts. The trigger uses only arrived work: residual queue beyond
regular capacity over the booking lead time, less already-booked capacity. No
future arrivals or future peaks are visible to the policy. Bookings cannot be
cancelled, so idle temporary shifts are paid. Outstanding commitments beyond
the replay end are charged separately, but do not create in-window completions.

Permanent additions are available from the first day. Thus these are capacity
options, not a recruiting timeline. Benefits, onboarding, hiring costs, fatigue,
legal constraints, skills, packing and late-delivery penalties are omitted.

## Interpretation

- Do not add labor solely because some backlog exists: the base case already
  reaches the selected service target without interventions.
- Persistent absence plus low productivity can cause a cumulative queue; service
  collapses nonlinearly when throughput stays below demand.
- If coverage of all listed stresses is required, nine with overtime is the
  least expensive tested robust option under these cost assumptions.
- Temporary policies here cannot repair every stress. This is evidence about
  the chosen limits and reactive booking rule, not temporary labor in general.
- The robust policy only narrowly exceeds 95% in its worst case. Do not describe
  it as a guarantee against untested conditions or call its cost optimal.
- Exact cost rankings depend on illustrative prices. Dollar savings should not
  be claimed as real business impact. No probabilities are assigned to stresses.

## Reproduce

```bash
python3 scripts/compare_service_costs.py
PYTHONPATH=src python3 -m unittest discover -s tests
```

Outputs in `data/processed/service_costs/`: `cases.csv` contains all 1,080 runs,
`policy_robustness.csv` compares all 30 policies, and `summary.json` captures
chosen policies, full assumptions and input hashes. Existing dashboard outputs
are unchanged. Tests verify no-action equivalence with the prior service engine,
overtime caps/costs, paid absence, delayed bookings and uncancellable shift costs.

Demand source: Rodrigo Furlan de Assis, Order Picking Dataset from a Warehouse
of a Footwear Manufacturing Company, DOI 10.17632/pf2w725pw3.1, CC BY 4.0.
Creation-date demand is transformed for replay; these results do not describe
the source company's actual staffing, compensation or performance.
