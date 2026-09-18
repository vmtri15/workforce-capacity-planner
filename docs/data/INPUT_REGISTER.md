# Model Input Register

## Rule for Phase 1

Every model input must be classified as **observed**, **estimated**, or
**assumed**. The application must show this classification next to the input;
it cannot present a regional benchmark or a simulated value as facility data.

## Inputs available now

| Input | Classification | Source field or source | Use in the model | Material limit |
| --- | --- | --- | --- | --- |
| Historical order date/time | Observed | UCI Online Retail II: `InvoiceDate` | Shape daily/weekly demand scenarios after documented aggregation | UK retail transactions from 2009–2011; not U.S. warehouse arrivals |
| Historical line quantity | Observed | UCI: `Quantity` | Build units and order-line mix scenarios | Cancellations/returns can create non-positive quantities; clean explicitly |
| Historical order identifier | Observed | UCI: `Invoice` | Derive orders, lines per order, and units per order | Invoice semantics must be documented after cleaning |
| Warehouse wave identifier | Observed | Warehouse Picking: `waveNumber` | Model work-release batches and compare wave mix | No start/end timestamps |
| Pick quantity and location | Observed | Warehouse Picking: `quantityToPick (units)`, `locations` | Create complexity proxies such as lines, units, and locations per wave | Location count is not travel time or labor duration |
| Assigned operator ID | Observed | Warehouse Picking: `operator` | Describe observed operator allocation only | No clock-in/out fields, so it cannot derive picks per labor hour |
| Footwear source package | Duplicate observed source | Extracted Mendeley footwear archive | Preserve layouts, storage alternatives, and source documentation | `Customer_Order.csv` and `Picking_Wave.csv` match the existing `warehouse_picking` copies by SHA-256; do not double-count them |
| Preparation time and operational exceptions | External benchmark pending review | Soto-Pinedo 2024-2025 workbooks | Potentially benchmark preparation time, picking errors, receiving incidents, and overtime sensitivity | Different organization and geography; contains identifiable operational fields and no license file in the archive, so use only de-identified aggregates after license confirmation |
| Regional warehousing employment/payroll | Observed | Census CBP 2023, NAICS 493 | Regional context and labor-cost plausibility checks | County-wide, multi-employer, and not e-commerce-only |
| Employment, hires, separations | Observed when queried | Census QWI API, county + NAICS | External labor-market context | Aggregate industry flows, not a facility recruiting pipeline |
| Role tasks and skills | Observed | O*NET Database 31.0 | Role definitions and training/skill considerations | Not wage, productivity, or staffing evidence |
| Role wage benchmark | Observed when saved | BLS OEWS by SOC and benchmark area | Labor-cost scenario input | Area-wide wage estimate, not an offer rate or total employment cost |
| Productive units per hour | Assumed, pending calibration | Low/base/high user-controlled parameter | Convert workload to direct labor hours | No current source connects the available task records to time worked |
| Shift length, breaks, absenteeism, overtime cap | Assumed | Editable scenario controls | Convert scheduled people to usable labor hours | Must be shown as scenario assumptions |
| Training days, hiring lead time, temporary labor availability | Assumed or estimated | Editable scenario controls; future source may support ranges | Determine readiness date and response options | Do not present as observed company process data |

## First capacity formula

For each site, day, and direct-production role:

`required productive hours = workload units / assumed productive units per hour`

`available productive hours = scheduled people × paid hours × utilization factor`

`capacity gap = required productive hours − available productive hours`

The model must retain the two components separately. A positive gap does not
automatically mean hiring: it triggers comparison of overtime, temporary labor,
training, hiring, or an explicitly feasible workload move.

## Data preparation decisions still required

1. Select a planning grain: daily workload with intra-day cutoff flags is the
   recommended starting point.
2. Define the order cleaning rule for cancelled/returned UCI invoice lines.
3. Define the mapping from UCI retail transactions to modeled fulfillment units;
   preserve the source's original country and period in the provenance record.
4. Calculate wave-level features from the warehouse file without inferring time
   or productivity.
5. Add a source-backed productivity range before using model outputs as more
   than an exploratory scenario tool.
