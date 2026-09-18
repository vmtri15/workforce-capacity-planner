# Productivity Research and Modeling Decision

## What the evidence supports

The picking productivity unit for this project is **order
lines per productive labor hour**. Packing requires a separate task boundary and unit.
Order-line volume is available in the cleaned UCI profile and is more comparable
when an order can contain multiple items.

Warehouse-performance literature identifies order lines picked per labor hour
as a standard order-picking productivity measure. A 2021 retail-warehouse case
study reported 60 order lines per working hour for its single-picking strategy;
its batching/sorting processes used different rates. That is useful as an
initial manual-picking anchor, but it is not an Illinois/Wisconsin facility
standard, an e-commerce promise, or a packing rate.

Sources:

- [Warehouse KPI framework](https://doi.org/10.1108/MABR-03-2020-0018)
- [Retail warehouse case study](https://www.mdpi.com/2227-9717/9/6/1061)

## Why a single published rate would be misleading

The available benchmarks vary by picking technology, travel distance, product
size, automation, order mix, batching, and whether the measure refers to a
line, item, case, or order. For example, the case study reports 60 lines/hour
for single picking and different rates for retrieval and sorting. A NIST report
describes approximately 150 **cases** per hour in a voice-pick grocery setting,
which is not comparable to e-commerce order lines.

The local warehouse-wave data has quantities, locations, waves, and operators,
but no time worked. It therefore cannot calibrate a rate.

## Phase 1 modeling decision

Use a manual-picking **sensitivity** rather than claim a validated standard:

| Case | Productive lines per hour | Meaning |
| --- | ---: | --- |
| Low | 45 | Conservative planning sensitivity |
| Base | 60 | Source-informed manual single-picking anchor |
| High | 90 | Illustrative improvement sensitivity, not an automation benchmark |

The model must label all three values as `assumed — source-informed,
uncalibrated`. The values control direct-picking hours only. Packing uses a
separate editable labor-hour factor until a process-specific time source is
available.

## Calibration requirement for a production-style claim

Before presenting a rate as calibrated, obtain a WMS/labor-management extract
that joins at least:

- worker or work-team identifier,
- process (pick versus pack),
- start and completion timestamp or paid productive minutes,
- lines, units, and complexity fields,
- shift/date and exception flags.

Then calculate productivity by process and complexity segment, remove defined
exceptions, and validate the rate on a later period. Until then, model results
are scenario comparisons, not claims about a real facility's required staffing.

## September 15 literature review

See [Workforce learning and cross-training evidence](WORKFORCE_LEARNING_RESEARCH.md) for five full-text reviews, page references, applicability limits, and the packing research priority. Existing numerical model assumptions remain unchanged.

## Packing review and implementation design — September 15

See [Packing evidence and model design](PACKING_RESEARCH.md). The current code uses pack jobs/hour and one assumed package/order. The proposed extension separates per-package and per-unit work. The invoice profiler currently counts all invoice IDs, so an outbound-order and order-mix audit precedes implementation. Reviewed studies support model structure, not calibrated coefficients.
