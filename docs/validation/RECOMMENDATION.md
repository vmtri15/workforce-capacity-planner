# Conditional Recommendation After Validation

## Decision

Do not present six workers, or nine workers plus overtime, as reliably meeting
95% two-operating-day unit service across time. Both passed their original
selection criteria but failed those criteria in at least one later-period case.

For the portfolio, recommend **scenario-based staffing with explicit service-risk
limits**, not an unconditional fixed headcount. The frozen six-worker and
nine-worker choices both failed at least one later-period criterion. A separate
post-evaluation search identifies six workers with capped overtime as the
affordable later-period base response and ten with capped overtime as the
lowest worst-case-cost response passing every listed later-period stress. These
are conditional scenario results, not validated staffing prescriptions.

## Price Sensitivity

Repriced all previously simulated policies under 27 combinations:
- Regular hourly cost: hypothetical $18, $22, $28.
- Overtime multiplier: 1.25, 1.5, 2.0.
- Temporary hourly cost: hypothetical $24, $30, $40.

Six without actions remained the cheapest passing full-period base-case policy
in all 27 combinations. Nine with capped overtime remained the lowest worst-case
cost policy passing all full-period stress cases in all 27 combinations.
These are bounded sensitivities, not evidence of stability at every possible
price or an empirical probability. Policy actions were held fixed: their rules
do not depend on price, so repricing requires no new capacity simulation.

## Chronological Check

Selected policies using order creation dates in January-June 2023, then evaluated
the frozen choices on July-October 2023. No replacement policy was selected after
observing the evaluation results.

| Selected policy and criterion | Later-period result | Conclusion |
| --- | --- | --- |
| Six workers, no actions; 40 units/hour, no absence | 92.74% on time | Fails 95% |
| Nine workers, up to two overtime hours per present worker; every listed stress | 32/36 cases pass; worst 91.90% | Fails all-stress criterion |

All four failed stress-grid entries for nine plus overtime have 30 units per
productive hour and two persistently absent workers. Retained demand reaches
91.90%; deduplicated demand reaches 92.92%. Each is repeated for two temporary
lead times, which are irrelevant to a policy without temporary workers. Thus
32/36 is grid coverage, not 36 independent trials or an estimated success rate.

Practical scenario recommendation: do not assume nine scheduled workers plus
overtime will protect the two-day target when only seven are present at the low
productivity assumption. Flag this combination as a service-risk condition and
require a different coverage plan or an explicitly relaxed service promise.
## Exploratory Replacement Search

After preserving the frozen-policy validation above, all 30 predefined policies
were evaluated on the later period. This is a post-hoc decision analysis, not a
new holdout validation.

| Objective | Exploratory later-period policy | Result |
| --- | --- | --- |
| Affordable base response | Six workers, up to two overtime hours | 96.08% on time; modeled cost $106,326; 12/36 listed stresses pass |
| Lowest-risk tested response | Ten workers, up to two overtime hours | 36/36 listed stresses pass; worst service 96.08%; maximum modeled cost $176,616 |

Use the six-worker overtime policy only when productivity is near 40 units per
productive hour and attendance is stable. Use the ten-worker overtime policy
when low productivity or two-worker absence is a planning concern. Costs remain
hypothetical and do not establish savings.

## Important Limits

This is an exploratory chronological robustness check, **not an untouched test**:
the full dataset and its patterns were inspected earlier. Each period starts with
zero backlog and bookings and receives its own 28-day zero-arrival recovery tail.
The selection tail does not use later-period arrivals. This isolates demand
periods, but it is not continuous deployment with inherited backlog or bookings.
Orders are represented as divisible units, not whole-order shipping deadlines.
Staffing, productivity, attendance, costs and deadlines remain hypothetical.

The full-period pass and later-period failure are not contradictory: an aggregate
service percentage can hide weaker performance in a particular period. The
dashboard should show period-specific performance and these failure conditions,
not only a green full-period indicator.

## Reproduction

```bash
python3 scripts/validate_recommendations.py
PYTHONPATH=src python3 -m unittest discover -s tests
```

Outputs in `data/processed/recommendation_validation/`:
- `price_sensitivity.csv`: 27 price combinations and chosen policies.
- `selection_cases.csv`: 1,080 earlier-period cases.
- `evaluation_cases.csv`: 72 later-period cases for the two frozen policies.
- `exploratory_replacement_cases.csv`: 1,080 later-period cases across all 30 predefined policies.
- `summary.json`: selections, evaluation, source fingerprints and limitations.

Input fingerprints must match the saved cost analysis before repricing. All
selection/evaluation workload totals reconcile and no deadlines remain censored.
The direct site-and-action answer is generated in `../../DECISION_ANSWER.md` and shown
in the dashboard Recommendations view.

Source demand: Rodrigo Furlan de Assis, Order Picking Dataset from a Warehouse
of a Footwear Manufacturing Company, DOI 10.17632/pf2w725pw3.1, CC BY 4.0.
This analysis does not describe the company's actual staffing or service quality.
