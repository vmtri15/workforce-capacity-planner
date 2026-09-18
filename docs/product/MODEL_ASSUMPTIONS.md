# Initial Model Assumptions

## Modeling scope

The first capacity model covers an eight-week peak-demand period for three
modeled fulfillment sites. It evaluates daily picking and packing capacity,
same-day workload coverage, and direct wage cost. It does not represent any
identified company's facilities or workforce.

## Planning period

| Input | Initial value | Classification | Basis |
| --- | ---: | --- | --- |
| Planning grain | Daily | Design decision | The source supports dates, but not reliable within-day operational cutoffs. |
| Planning horizon | 56 calendar days | Design decision | Eight weeks shows weekday and peak patterns while remaining usable for staffing decisions. |
| Historical pattern window | 2011-10-14 to 2011-12-08 | Observed/source-derived | Highest consecutive 56-day order-line total in the cleaned UCI history. |
| Source order lines | 141,080 | Observed/source-derived | Cleaned positive-quantity order lines in the selected window. |
| Source orders | 5,903 | Observed/source-derived | Distinct invoice IDs in the selected window. |
| Demand scale | 5.0x | Assumed | Creates a portfolio-sized modeled operation without claiming local observed demand. |
| Modeled order lines | 705,400 | Scenario-derived | Source order lines multiplied by demand scale. |
| Modeled orders | 29,515 | Scenario-derived | Source orders multiplied by demand scale. |

All source dates remain historical. The engine creates one planning row for
every calendar date in the window and preserves the historical source date when
a source record exists. Eight dates have no source record and are represented
as explicit zero-demand dates; this is an absence-of-record convention, not
evidence that the business was open with zero demand.

## Site allocation

The initial demand allocation uses the relative 2025 Q4 QCEW NAICS 493
employment across the study geographies as a transparent sizing proxy.

| Modeled site | Allocation | QCEW employment used |
| --- | ---: | ---: |
| Joliet/Elwood | 43% | 28,283 |
| O'Hare area | 42% | 27,742: Cook plus DuPage |
| Kenosha/Pleasant Prairie | 15% | 9,678 |

The rounded shares sum to 100%. County employment is not facility workload, so
the application must expose these shares as editable assumptions.

## Operating assumptions

| Input | Initial value | Classification |
| --- | ---: | --- |
| Operating shifts | Two per day | Assumed |
| Paid hours per shift | 8.0 | Assumed |
| Productive-time factor | 85% | Assumed |
| Productive hours per scheduled person | 6.8 | Scenario-derived |
| Day/evening workload split | 60% / 40% | Assumed |
| Baseline absence | 0% | Assumed; absence is applied as a separate stress scenario |
| Service target | At least 95% of modeled daily workload completed by end of day | Assumed |

The source data does not support an intraday promise, so the first version uses
an end-of-day target. The shift split affects coverage presentation and remains
editable.

## Productivity cases

| Process | Low | Base | High | Unit and status |
| --- | ---: | ---: | ---: | --- |
| Picking | 45 | 60 | 90 | Order lines per productive hour; source-informed, uncalibrated |
| Packing | 35 | 50 | 65 | Pack jobs per productive hour; source-informed sensitivity |
| Packages per modeled order | 1.0 | 1.0 | 1.0 | Assumed simplification; UCI does not contain parcel count |

The picking base uses the published 60-line/hour single-picking case-study
value. The packing base uses a reported 50-package/hour workplace norm only as
an exploratory anchor. Neither is a local standard. Picking and packing remain
separate calculations.

## Initial active staffing for the base case

The scaled daily workload has a 95th percentile of 21,475 order lines and 850
orders. With 60 pick lines/hour, 50 pack jobs/hour, and 6.8 productive
hours/person, the initial active staffing is:

| Modeled site | Pickers | Packers | Supervisors | Shipping/receiving coordinators | Total active staff/day |
| --- | ---: | ---: | ---: | ---: | ---: |
| Joliet/Elwood | 23 | 2 | 2 | 1 | 28 |
| O'Hare area | 23 | 2 | 2 | 1 | 28 |
| Kenosha/Pleasant Prairie | 8 | 2 | 2 | 1 | 13 |
| Total | 54 | 6 | 6 | 3 | 69 |

Picker and packer counts are calculation outputs rounded up to whole people.
Packing retains at least one packer per operating shift. Supervisor coverage is
one per site per shift; coordinator coverage is one per site per operating day.
Those coverage rules are policy assumptions, not inferred productivity ratios.

These are active daily positions. Phase 3B constructs a minimum synthetic roster
of 102 people to cover them with at most five regular paid days per rolling
seven-day window. This assumes unrestricted availability and does not include
absence or training coverage; see `../validation/PHASE_3B_RESULTS.md`.

## Model controls that remain editable

- demand scale and site shares;
- productivity case and productive-time factor;
- shift split and service target;
- packages per order;
- absence, overtime, temporary labor, hiring, and training scenario inputs;
- wage basis and loaded-labor multiplier.

## Sources

- Cleaned daily workload: `data/processed/uci_daily_workload_profile.csv`
- QCEW benchmarks: `data/raw/bls/workforce-qcew-2025q4-493.csv`
- Wage benchmarks: `data/processed/oews_2025_role_wage_benchmarks.csv`
- Picking evidence: https://www.mdpi.com/2227-9717/9/6/1061
- Packing-context evidence: https://link.springer.com/article/10.1007/s10611-026-10296-z
