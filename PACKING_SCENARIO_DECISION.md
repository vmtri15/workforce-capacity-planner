# Reviewed codes and individual-unit packing scenario

September 15, 2026. Status: implemented and tested as a separate diagnostic. Not integrated into the optimizer; no calibrated staffing result.

Follow-up September 15: the separate opt-in integration is now implemented in
`scripts/run_packing_optimization.py`. See `PACKING_INTEGRATION_RESULTS.md`.
The original diagnostic and legacy results described below remain preserved.

## Reviewed code decisions

Read all distinct nonstandard codes and their descriptions from the first audit. Normalize code case. Exclude POST/DOT postage, C2 carriage, BANK CHARGES, AMAZONFEE, D discount, M/m manual accounting entries, ADJUST/ADJUST2/B adjustments and TEST001/TEST002 test records from candidate merchandise. Treating all manual entries as nonmerchandise is a conservative policy, not proof that they never involve fulfillment.

Restore described physical products for explicitly listed DCGS codes, PADS and SP1002. Do not infer that every DCGS-prefixed record is merchandise. Blank descriptions remain unresolved even for a known code. Exact administrative descriptions update/check/found/adjustment/damaged are flagged for review, including on ordinary numeric codes. This is a limited screen, not exhaustive semantic cleaning.

Vouchers and samples remain in review because fulfillment mode is unknown. Full-history unresolved review: 1,608 blank-description rows, 102 voucher/sample rows and 98 administrative-description rows. They are excluded from the candidate scenario, not silently declared nonexistent demand. The reviewed review CSV retains their codes, descriptions and counts.

## Revised source totals

Planning window October 14–December 8, 2011, before 5× scenario scaling: 4,697 candidate orders; 140,447 lines; 1,336,389 units. Median 164 units/order, mean 284.52. These supersede the initial conservative-screen counts for the reviewed scenario only. Restored product rows increase some counts while administrative-description filtering removes other rows/orders.

The entire 604-day source profile still reconciles exactly to the legacy dates, line, invoice and unit totals before classification. Known 22,523 overlapping rows remain excluded. Old audit artifacts are preserved; reviewed artifacts use the `reviewed_` prefix.

## Scenario decision

Use individual-unit handling as an explicit diagnostic assumption. Retain all candidate order sizes; do not invent case-pack quantities or trim large orders merely to match a small-parcel story. One source unit is not proven to be one physical piece, so even individual-unit handling remains an assumption.

Estimate packing jobs per order as `ceil(order_units / assumed_units_per_job)`. A job is an abstract unit-count packing-work proxy, not a dimensionally verified carton. Use 12/24/48 units per job as an arbitrary sensitivity grid, with no preferred calibrated base value. It does not imply any actual box fits that many products. Actual cartonization needs SKU dimensions/weights and packaging constraints.

Round per order before aggregation and scale the resulting order workload by the existing factor of five. Retain the joint order-unit distribution through a date/lines/units/count histogram without customer or invoice identifiers.

Basic productive packing hours = `(estimated_jobs × fixed_seconds_per_job + units × seconds_per_unit) / 3600`.

The thesis illustration of 67.2 fixed seconds and 4.2 seconds/unit is retained solely for comparability with the earlier diagnostic. It is not adopted as a measured rate for this source mix. No break allowance is embedded; future integration must apply productive availability once.

## Diagnostic results

| Assumed units per job | Estimated jobs at 5× scale | Basic productive hours |
|---|---:|---:|
| 12 | 566,925 | 18,378.20 |
| 24 | 289,395 | 13,197.64 |
| 48 | 150,935 | 10,613.06 |

Full workload before service-target or scheduling constraints. These are assumption sensitivities, not actual facility needs or savings. No inference of a calibrated base case follows from the middle value. Existing Phase 3C optimizer/database results remain unchanged.

## Artifacts and reproduction

- `config/packing_scenario.json`: explicit scenario and evidence classifications.
- `scripts/audit_outbound_orders.py --reviewed`: reviewed source audit and anonymous order-mix histogram.
- `scripts/build_packing_scenario.py`: three 56-day demand series and reconciliation checks.
- `data/processed/reviewed_outbound_audit.json`: counts and source hash.
- `data/processed/reviewed_outbound_code_review.csv`: unresolved records.
- `data/processed/reviewed_order_mix.csv`: anonymous order-size histogram.
- `data/processed/packing_scenario_daily.csv` and `packing_scenario_results.json`: diagnostic outputs.

Validation: 11 audit tests and 8 packing tests pass; each scenario contains 56 dates, preserves candidate order and unit totals, and has monotonic hours across job-size sensitivities. Test per-order rounding to prevent merging unrelated orders into one job. Solver code was not modified, so no new optimizer feasibility/optimality claim is made.

Next: integrate an opt-in productive-hour demand interface in the optimizer, preserving the historical baseline and representing infeasibility honestly under unchanged staffing. The interface must use the same productive-hour unit for overtime, temporary staff, hiring and cross-training donor losses. Carry the scenario's uncalibrated status into every output; do not display estimated jobs as observed parcels.
