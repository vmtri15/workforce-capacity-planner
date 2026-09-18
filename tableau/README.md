# Tableau Portfolio Data Package

This is a local data package, not a completed Tableau workbook or published site.
Rebuild with `python3 scripts/export_tableau.py` from the project directory.
No customer, order or employee identifiers are included. Product references remain
in aggregated rankings. No OpenPack or recruiting records are in this package.

## O*NET 2026 Role Evidence

The companion `onet_2026/` folder contains four occupations, 77 task statements,
40 essential-skill importance records and 100 transferable-skill importance
records extracted from O*NET 31.0 (August 2026). Rebuild with
`python3 scripts/export_onet_roles.py` using the project's openpyxl dependency.
The pre-existing local source release was verified from its Read Me; this is a
pinned local extract, not a new API fetch. Source fingerprints are in its manifest.

Use `occupation_data.csv` as the role dimension (`role_id` unique). Relate task
and skill tables separately to it, many-to-one on `role_id`. Do not physically
join tasks to skills: that multiplies rows. These are separate role-evidence
sources; the single-pool staffing scenarios do not have a role breakdown and
must not be assigned arbitrary role joins.

Record dates for the selected task and skill tables:

| Role | Source record date |
| --- | --- |
| Fulfillment associate | August 2026 |
| Packing associate | August 2020 |
| Shipping/receiving coordinator | August 2019 |
| Warehouse supervisor | August 2024 |

These are dates reported in the source, not verified survey collection dates.
Keep the date distinct from the August 2026 release label. Skill values use the
Importance scale only; preserve suppression and not-relevant flags, and exclude
suppressed ratings from comparison. Do not sum ratings across roles or infer
training duration, staffing requirements or individual worker ability from them.

Attribution: O*NET 31.0 Database, U.S. Department of Labor, Employment and Training
Administration, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
Transformed by selecting four occupations and importance-scale skill records.
Source: https://www.onetcenter.org/database.html. No endorsement implied.

## Data Model

| File in data/ | One row represents | Use |
| --- | --- | --- |
| demand_daily.csv | Source date, order-size segment and duplicate basis | Demand and order mix |
| scenario_results.csv | Period, policy, duplicate basis, rate, absence and lead time | Cost and service comparison |
| policies.csv | One staffing policy | Policy labels and limits |
| price_sensitivity.csv | One hypothetical price combination | Stability of selected policies |
| monthly_top_products.csv | One month's top-10 product reference | Product concentration |

Only relate `scenario_results.policy` to `policies.policy`, many to one.
Keep the other tables as independent data sources. Do not physically join demand
to scenarios by date, basis or period: each scenario repeats the same demand.
Do not join price winners to scenario rows and then sum duplicated costs.
Unique keys and policy foreign keys are validated in the export.

## Definitions and Aggregation

- `basis`: retained source rows or deduplicated sensitivity. Select exactly one;
  never sum both. Duplicates have not been proven erroneous.
- `segment`: 1-5 units or more than five units per order; a zero category is
  supported if present. These are order-size groups, not measured labor classes.
- `orders`, `units`: additive across dates and segments within one basis.
  Missing dates are not represented and are not confirmed zero demand.
- `period`: full historical window, earlier selection period, or later evaluation.
  These overlap; never sum across periods. Evaluation contains only the two
  frozen selected policies. Missing policy-period combinations are unavailable,
  not zero-cost or failed runs.
- `workers`, `absent`, `present_workers`, `rate`, `lead_days`, `service_days`:
  scenario dimensions, not additive measures. Rate is units/productive hour.
- `on_time_unit_share`: fraction, format as a percentage. At a single case it
  equals completed_on_time / arrivals. Do not average cases into a success rate.
- `target_met`: saved scenario status; the assumed target is 0.95 within two
  operating days. It describes units processed, not whole orders shipped.
- `total_cost`: hypothetical USD for the displayed period including recovery and
  outstanding temporary commitments. Compare one case per policy, never sum
  mutually exclusive scenarios or compare different-length periods as savings.
- `peak_backlog`: maximum daily closing units in a replay, never additive.
- `backlog_unit_days`: sum of daily closing queue units, not exact waiting time.
- `completed_late`, `overdue_unfinished`: failures of the service target.
- `pending_not_due`: censored work; a nonzero value prevents a final pass label.
- `month_unit_share`: product units divided by all source units that month, not
  only the top ten. This table omits other products; do not report its sum as all
  warehouse demand. Basis is retained only. Reference is not reference-plus-size.
- `base_choice`, `robust_choice`: selected policy identifiers under a price set;
  these are full-period selections, not proof of later-period success.

Data types: dates as dates, key/category/policy/reference fields as text, counts
as integers, costs/rates/shares as decimal numbers, target_met as boolean.
Preserve product references as text. Do not use automatic numeric sums for IDs.

## Three Dashboard Views

1. Demand and Workload: recorded-date volume, order-size share and monthly top
   references. Default basis retained. Show duplicate sensitivity and incomplete
   calendar coverage. Do not label one partial year as established seasonality.
2. Staffing and Cost: policy cost versus unit-service percentage, with a 95%
   reference line. Single-select period, basis, rate, absence and lead time.
   Defaults: full, retained, 40, zero absence, one-day lead. Display the current
   assumptions and cost period beside the results. Filters select saved scenarios;
   they do not rerun Python or support arbitrary unmodeled inputs.
3. Recommendation Risks: selection versus evaluation for the two frozen choices,
   stress-case failures, and price sensitivity. Show the full-period pass alongside
   the later failure. Nine plus overtime failed the low-rate/two-absence case.
   Repeated lead-time cases without temporary workers are not independent trials.

Required evidence labels: observed demand aggregation; hypothetical staffing and
costs; exploratory chronological check, not untouched validation. Earlier and
later periods start with zero backlog independently and have recovery tails.

## Acceptance Checks

- Retained demand: 32,634 orders and 228,195 units.
- Deduplicated sensitivity: 32,634 orders and 215,460 units.
- One full-period case, six workers, rate 40, no absence, no actions:
  95.807971% unit service and $238,656 modeled cost.
- Later evaluation of that base case: 92.735382% service.
- Later evaluation, nine plus overtime, rate 30, two absent, retained:
  91.898804% service. Must be shown as below target, not a recommended pass.
- 30 policy keys, 2,232 scenario records and 27 price combinations.

The package has been checked for keys and source totals, not rendered in Tableau.
Actual workbook interactions and display still need verification after import.

## Attribution and Publishing

Source: Rodrigo Furlan de Assis, Order Picking Dataset from a Warehouse of a
Footwear Manufacturing Company, DOI 10.17632/pf2w725pw3.1, version 1.
License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/.
Data is aggregated and transformed; simulations are our assumptions, not source
findings or endorsement. Keep this attribution with the published visualization.

Publication remains a separate step requiring review. Only the aggregate files
in data/ are intended for import. Do not upload raw folders, API credentials,
private files or the entire project. `manifest.json` records relative source
paths and fingerprints for local reproducibility; it is not a Tableau data table.
