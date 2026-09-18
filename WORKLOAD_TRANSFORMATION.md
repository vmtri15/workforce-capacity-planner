# Workload Transformation Design

## Objective

Create a reproducible **modeled daily fulfillment demand** series from public
historical order data. The result is a scenario driver, not measured workload
at any Illinois or Wisconsin facility.

## Source tables

| Source | Relevant fields | What it provides | What it cannot provide |
| --- | --- | --- | --- |
| UCI Online Retail II | `Invoice`, `StockCode`, `Quantity`, `InvoiceDate`, `Customer ID`, `Country` | Order-line timing, ordered quantity, and order-size distribution | U.S. facility arrivals, cutoff times, pick duration, worker schedule, or labor productivity |
| Warehouse Picking Dataset | `waveNumber`, `reference`, `quantityToPick (units)`, `locations`, `operator`, `creationDate` | Wave structure, pick quantities, locations, and operator assignment | Start/end time, travel time, paid hours, or picks per worker-hour |

## Cleaning rules for UCI transactions

1. Read both workbook sheets and retain the source-sheet name.
2. Convert `InvoiceDate` to a local planning date. Preserve its original
   timestamp in the raw staging table.
3. Mark, rather than silently delete, rows with `Quantity <= 0`. Use only
   positive-quantity rows for the outbound demand baseline unless a dedicated
   returns scenario is added.
4. Treat an invoice as an order candidate. Document any invoice prefix or
   duplicate rule after profiling the full file; never assume that every row is
   a separate order.
5. Retain `Country` in staging. The selected model uses the data only for
   seasonality and order-mix shape, never as proof of Chicago-area demand.
6. Check the overlapping dates around December 2010 across workbook sheets
   before concatenating. The audit found 22,523 exact repeated rows across
   December 1–9, 2010; retain the first-sheet records and exclude those dates
   from the second sheet.

## Daily modeled-demand table

The first model needs one row per planning day and site.

| Field | Definition | Classification |
| --- | --- | --- |
| `planning_date` | Calendar day from the cleaned source timestamp | Observed source-derived |
| `source_orders` | Distinct valid invoice IDs for the day | Observed source-derived |
| `source_order_lines` | Count of valid positive-quantity lines | Observed source-derived |
| `source_units` | Sum of valid positive quantities | Observed source-derived |
| `site` | Joliet/Elwood, O'Hare, or Kenosha/Pleasant Prairie | Assumed scenario allocation |
| `modeled_units` | `source_units × demand_scale × site_share` | Estimated/scenario-derived |
| `modeled_lines` | `source_order_lines × demand_scale × site_share` | Estimated/scenario-derived |
| `demand_case` | Baseline, surge, or disruption label | Assumed scenario control |

`demand_scale` establishes a portfolio-sized modeled operation. `site_share`
must sum to 100% for each date. Neither value is a public observation of a
study area or facility.

## Wave-complexity features

Build a separate `wave_features` table from the warehouse-picking data:

| Feature | Calculation | Use |
| --- | --- | --- |
| `wave_units` | Sum `quantityToPick (units)` by `waveNumber` | Work-size distribution |
| `wave_lines` | Count records by `waveNumber` | Work-complexity proxy |
| `wave_locations` | Distinct nonblank `locations` by `waveNumber` | Travel/slotting complexity proxy |
| `assigned_operators` | Distinct `operator` by `waveNumber` | Allocation-description field only |

These features may stratify low/medium/high complexity demand. They must not
be divided by operator count to create a productivity rate because the dataset
has no observed work duration.

## Link to staffing model

The current capacity engine uses modeled order lines for picking and estimated
pack jobs for packing, each divided by its separate assumed productive-hour rate.
The proposed package-plus-unit packing model is specified in `PACKING_RESEARCH.md`.

The user can vary low/base/high productivity and demand cases. Outputs must
state that the sensitivity is a planning scenario until a time-stamped labor
source supports calibration.

## Acceptance checks before implementation

- Daily dates are continuous or missing dates are explicitly explained.
- Positive units, lines, and orders are all nonnegative after cleaning.
- Site shares sum to 100% for every planning date.
- The raw source fields stay traceable to every derived workload field.
- No `operator`, `wave`, or location field is used as a proxy for hours worked.

## Completed source profile

`data/processed/uci_daily_workload_profile.csv` is the deduplicated,
source-derived daily profile. It contains 604 days from 2009-12-01 through
2011-12-09, 11,490,122 positive-quantity units, 1,022,291 positive-quantity
lines, and 22,557 non-positive-quantity lines. Those non-positive lines remain
visible for a future returns treatment and are excluded from the outbound-unit
baseline.

## September 15 source-definition correction

The existing `distinct_invoice_ids` field counts all invoice IDs before quantity filtering. It must not be described as cleaned valid outbound orders. Preserve it for provenance and derive a separate outbound-order measure through the audit specified in `PACKING_RESEARCH.md`. Parcel counts remain assumed.
