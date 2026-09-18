# Packing evidence and model design

Reviewed September 15, 2026. Status: full-text review complete; standalone packing calculation and candidate audit implemented. Optimizer integration and calibration remain pending. See `../validation/OUTBOUND_AUDIT_RESULTS.md`.

## Sources and applicability

### Judith Weiblen (2014), Determining Cycle Times for Packing in Distribution Centres

Source: `/Users/minhtrivi/Downloads/Cycle Times for Packing.pdf`. KIT thesis, ISBN 978-3-7315-0202-9.

PDF pp. 146–149 (printed pp. 122–125): process decomposition and standard task times produce an average-case example based on characteristics of 58 packing processes. At 5.6 articles per package, calculated basic time is 90.7 seconds: 8.8 setup + 51.8 base + 5.6 × 4.2 item handling + 5.4 steps + 1.2 turns. Travel is assumed zero. This is a constructed example, not an observed universal mean. The allowance-adjusted example is 114.8 seconds and still excludes some downtime and support work.

The empirical comparison covers 17 packing areas, with a median of 332.6 seconds/package and substantial dispersion. The author questions comparability and data quality; aggregate times may include waiting and other activities. Neither value calibrates our facilities.

Use: distinguish per-package work, per-item work, and separately scoped travel/support work. Do not transfer numerical coefficients without matching process boundaries.

### Mauluddin and Fardiansyah (2025), Karakuri Kaizen Design to Reduce Work Time at the Packing Station

Source: `/Users/minhtrivi/Downloads/Karakuri Kaizen Design to Reduce Work Time.pdf`. DOI: 10.12928/si.v23i2.330.

PDF pp. 6 and 8: chili-sauce manufacturing, 48 units of 135 g per carton. Reported station time changes from 158.08 to 24.74 seconds, but filling work is transferred/shared with Seal A and Seal B operators. The task scope and labor allocation change. This does not establish equivalent per-worker or system labor savings. The straightforward time reduction is 84.35%; the reported 109.08% improvement does not match that calculation.

Use: workstation and bottleneck redesign example only; not a mixed-order fulfillment packing-rate benchmark.

### Sara Pearson Specter (2015), 4 Ways Packing Stations Have Evolved

Source: `/Users/minhtrivi/Downloads/EBSCO Full Text Sept 15 2026 (1).pdf`. Modern Materials Handling, September 2015, pp. 38–43.

Trade article based on vendor interviews. PDF p. 2 gives a conditional 10–15-second saving from printer placement; other examples concern automated equipment and mobile pick/pack workflows. No matched labor-time dataset supports adopting these claims as manual packing rates.

Use: define equipment, ergonomics and included tasks; contextual evidence only.

## Current code and source audit

Inspected `src/workforce_planner/planning_engine.py`, `scripts/profile_uci_orders.py`, and `scripts/build_database.py`.

- Picking already uses order lines/hour. Packing uses pack jobs/hour (35/50/65), with packages_per_order = 1.0. Packing is not currently calculated in lines/hour.
- Daily source data contains positive quantity lines, positive units, and distinct invoice IDs. The profiler adds invoice IDs BEFORE checking Quantity > 0. Thus distinct_invoice_ids is not a cleaned outbound-order count and may include return-only invoices.
- Actual parcel counts, package dimensions, handling units versus cases, packing durations, and worker hours are absent.
- Daily aggregation loses order-level mix. Positive quantity alone does not establish that every record is a physical shippable product. Product-code and cancellation exclusions need an explicit audit.
- Site allocations independently round orders, lines and units. They preserve totals but do not preserve individual orders or their item associations.

## Proposed workload model

Picking retains its existing line-based sensitivity. Proposed packing productive hours:

`(modeled_packages × fixed_seconds_per_package + modeled_units × seconds_per_unit + separately_scoped_support_seconds) / 3600`

This is our simplified adaptation of the thesis structure, not its exact equation. Unit handling means individual units only if the selected scenario explicitly assumes that each positive unit is handled separately. Case handling requires another parameterization.

`modeled_packages = cleaned_outbound_orders × packages_per_order`

Package count is estimated, never observed. Fractional expected packages are acceptable for planning totals; use one documented rounding/allocation rule for discrete scenarios. Do not equate order lines, individual units, orders, and packages.

Keep task times as basic productive seconds. Apply the existing 0.85 productive-time factor once on available paid hours. Do not also incorporate overlapping break/recovery allowances in coefficients. Define support activities as either explicit workload or part of the factor, never both.

## Implementation sequence and acceptance criteria

1. Reprofile invoice-level outbound candidates from raw transactions. Retain original invoice count for provenance; add a separate cleaned outbound-order count. Audit cancellation/non-product rules and report excluded counts. Test mixed positive/negative invoices, return-only invoices, and missing IDs.
2. Publish units/order and lines/order distributions and extreme cases before choosing parcel/handling assumptions. Preserve historical date and duplicate rules.
3. Add an explicit opt-in package-plus-unit mode and editable coefficients, all labeled assumed and uncalibrated. Keep the existing rate baseline available for comparison; do not silently replace saved Phase 3C results.
4. Express packing demand and workforce actions consistently in productive hours throughout planning and optimization. A changing daily order mix cannot use an unchanged universal packages/hour conversion. Review cross-training donor losses, temporary workers, hires, and transfers for unit consistency.
5. Validate zero demand; doubling items with fixed packages; doubling packages with fixed items; site-total reconciliation; no allowance double counting; and feasible capacity accounting. Compare identical demand/staffing under both modes, with separate result identifiers.

Next implementation task: outbound invoice and order-mix audit. Broad packing literature search is paused. Numerical coefficients remain uncalibrated; no facility staffing claim follows from these sources.

## Reviewed scenario follow-up

See `../validation/PACKING_SCENARIO_DECISION.md` for the revised code review, candidate counts, per-order job-size sensitivities and validation. These remain separate diagnostic outputs, not calibrated rates or observed parcels.
