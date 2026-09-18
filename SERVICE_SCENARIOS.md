# Hypothetical Staffing and Service Scenarios

## Design

The grid in `config/footwear_scenarios.json` was specified before running results:
4-12 scheduled workers, 30/40/50 units per productive hour, 0/1/2 absent workers
each operating day, and one/two operating-day service windows. Each combination
is run with source rows retained and with exact duplicates removed as sensitivity:
324 historical replays. These are hypothetical inputs, not warehouse facts.

The objective is at least 95% of units processed by their deadline. The arrival
operating day counts as day one; arrivals on closed days start their clock on the
next operating day. Deadlines are inclusive at day end. All arrivals are assumed
available at day start. This is not whole-order completion or shipping service.

Other assumptions: Monday-Friday operation, eight paid hours, 85% productive time,
zero initial backlog, FIFO unit processing, no overtime or temporary workers, and
28 calendar days of zero arrivals after the source window. Missing source dates
assume zero demand. Absences are persistent stress levels, not measured patterns.

## Results

Retained demand, six scheduled workers, 40 units per productive hour:

| Absent every operating day | Within one operating day | Within two operating days |
| --- | ---: | ---: |
| 0 | 73.3% | 95.8% |
| 1 | 46.7% | 84.3% |
| 2 | 2.8% | 11.6% |

Low-capacity scenarios accumulate queues, so reductions need not be proportional
to headcount. A queue that eventually clears does not retroactively meet deadlines.

Lowest tested scheduled headcount meeting 95%, retained demand, no absences:

| Assumed units/productive hour | One operating day | Two operating days |
| --- | ---: | ---: |
| 30 | No passing value in 4-12 | 8 |
| 40 | 11 | 6 |
| 50 | 9 | 5 |

These are discrete grid thresholds under fixed assumptions, not recommendations
to hire those numbers. A threshold at the lower bound would not establish that
smaller untested values fail. The scenario range was not expanded to force a pass.

## Decisions Supported

- Agree on the service promise before declaring capacity sufficient or short.
- At the base assumed rate, six fully present workers narrowly pass the two-day
  target but not the one-day target. Do not describe this as universally adequate.
- Compare attendance coverage against a chosen target: persistent absence makes
  the same roster substantially less reliable in these replays.
- Show productivity and duplicate-data sensitivities, not a single hiring number.
- Overtime and temporary-response experiments remain separate in
  `OPERATIONAL_ACTIONS.md`; they are not silently included in these thresholds.

## Reproduction and Verification

```bash
python3 scripts/run_service_scenarios.py
PYTHONPATH=src python3 -m unittest discover -s tests
```

`data/processed/service_scenarios/` contains:
- `comparison.csv`: each scenario's service, overdue work and backlog measures.
- `staffing_thresholds.csv`: lowest passing tested headcount by assumptions.
- `daily.csv`: auditable daily arrivals, capacity, timely/late completion and queue.
- `manifest.json`: exact config, source fingerprints and metric definitions.

Units completed late remain failures. Unfinished overdue units remain failures;
unfinished units not yet due suppress the pass/fail label. All 324 current runs
have fully elapsed deadlines. Daily and scenario-level conservation and capacity
limits were checked. Tests cover weekend deadlines, late completion, absence,
censoring, invalid inputs and conservation. No existing dashboard data is changed.

Source: Rodrigo Furlan de Assis, Order Picking Dataset from a Warehouse of a
Footwear Manufacturing Company, version 1, DOI 10.17632/pf2w725pw3.1, CC BY 4.0.
Demand is aggregated from creation timestamps; no staffing or performance claims
about the source company are inferred. These are historical replays, not forecasts.
