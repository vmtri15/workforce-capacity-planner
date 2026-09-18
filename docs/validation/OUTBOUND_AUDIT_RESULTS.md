# Outbound audit and packing diagnostic

Verified September 15, 2026. This is a candidate-demand audit, not a validated shipment or parcel dataset.

## Results for the existing planning window

Source dates: October 14–December 8, 2011; figures below are before the existing 5× scenario scale.

| Measure | Existing profile | Candidate outbound screen |
|---|---:|---:|
| Invoice/order count | 5,903 | 4,759 |
| Positive lines | 141,080 | 140,506 |
| Positive units | 1,347,632 | 1,338,847 |

The order count falls 19.38%, while unit volume changes much less. There are 4,888 invoices with any positive quantity before the additional candidate screen. The 4,759 figure is not simply the result of removing returns: it also excludes review records.

Candidate orders: median 162 units, mean 281.33, p95 835, maximum 14,149. Median lines/order is 15, mean 29.52. Of 4,759 orders, 3,207 exceed 100 units and contain 1,264,029 of 1,338,847 units (94.41%). The source order mix does not substantiate a typical small consumer parcel or one parcel per invoice.

## Rules and limitations

The audit preserves the established second-sheet overlap exclusion through December 9, 2010. Classification precedence: missing invoice; C-prefixed cancellation; nonpositive quantity; nonstandard stock-code review; blank-description review; candidate outbound.

Candidate stock codes match five digits followed by optional letters and require a nonempty description. This is a reproducible screening assumption, not an authoritative product master. It leaves ordinary-looking inventory adjustments potentially unresolved and excludes some physical products with unusual codes. Do not call the output fully cleaned physical shipments.

Full-history categories: 1,015,916 candidate lines; 19,165 cancellation lines; 3,393 other nonpositive lines; 4,769 nonstandard-code review lines; 1,605 missing-description review lines. Review examples include POST/DOT postage, M manual entries, C2 carriage, bank charges, vouchers, but also DCGS product codes and PADS cushions. Inspect `data/processed/outbound_code_review.csv` before accepting or excluding unusual products. No customer identifiers are exported.

All 604 daily legacy date, invoice, line and unit values reconcile exactly; category counts reconcile to source rows. The 22,523 known overlap rows are excluded. No candidate invoice spans multiple dates.

## Packing implementation and diagnostic

Implemented `src/workforce_planner/packing.py` as a pure calculation of basic productive hours from packages, units, fixed package seconds, unit seconds and explicitly scoped support seconds. No hidden productive-time allowance is applied.

A separate comparison script requires explicit task-time coefficients. Its saved diagnostic uses 67.2 fixed seconds (8.8 + 51.8 + 5.4 + 1.2) and 4.2 seconds/unit from the thesis example solely to demonstrate sensitivity to source mix. These coefficients are not adopted operational defaults. One, two and four packages/order are arbitrary package-count stress cases, not empirical estimates or a validated range.

At the existing 5× demand scale:

| Diagnostic | Productive packing hours |
|---|---:|
| Existing invoice count at 50 pack jobs/hour | 590.30 |
| Candidate orders at 50 pack jobs/hour | 475.90 |
| Thesis task-time illustration, 1 package/order | 8,254.11 |
| Same illustration, 2 packages/order | 8,698.29 |
| Same illustration, 4 packages/order | 9,586.63 |

These are full-workload sums before service-target, availability or scheduling constraints. They do not measure actual labor requirements, and cannot be compared as improved cost/performance. Most of the difference comes from explicitly counting the large number of units. Existing Phase 3C results and database inputs are unchanged.

## Decision and next work

Retain UCI for historical timing and explicitly modeled demand. Do not automatically treat its large invoices as small-parcel orders. The next model-design step is a transparent order-mix scenario: define individual versus case handling and an assumed package construction rule, or constrain the prototype to an explicitly selected order-size segment and report excluded demand. Actual cartonization cannot be inferred without product dimensions/weights and packaging information. Keep the historical baseline available for comparison.

Before optimizer integration, resolve the code-review table and choose/document the scenario's handling unit and parcel assumptions. The network optimizer currently requires a constant productivity rate within each site/role group; variable package-plus-item workload must be passed consistently as productive-hour demand rather than silently changing daily rates.

## Reproduce and validation

Run with Python containing openpyxl:

```
python scripts/audit_outbound_orders.py
python scripts/compare_packing_workload.py --fixed-seconds 67.2 --seconds-per-unit 4.2
python -m unittest discover -s tests -p test_outbound_audit.py
python -m unittest discover -s tests -p test_packing.py
```

Seven audit tests and six packing tests pass. Coverage includes cancellation with positive quantity, mixed positive/negative invoices, return-only rows, missing IDs/descriptions, review codes, zero workload, item/package sensitivity, site reconciliation, invalid inputs and no hidden allowance. Legacy optimizer tests were not rerun because solver code and inputs were not modified.

Source file SHA-256: `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`. Machine-readable evidence: `data/processed/outbound_audit.json`, `outbound_daily_audit.csv`, `outbound_code_review.csv`, and `packing_workload_diagnostic.json`.
