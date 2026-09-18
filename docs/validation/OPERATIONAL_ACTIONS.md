# Operational Actions: Evidence and Decision Gates

All five analytical actions are implemented in `scripts/analyze_operational_actions.py`.
Outputs live in `data/processed/operational_actions/`. No dashboard, optimizer,
raw file, actual roster or warehouse layout has been changed.

## 1. Segment Workload

`orders_retained.csv` and `orders_deduplicated_sensitivity.csv` classify orders
as zero-unit, 1-5 units or above 5 units. `monthly_segments.csv` includes counts,
units and daily demand statistics. Order IDs are checked for consistent date and
customer before aggregation; no customer identities appear in outputs.

Large orders represent 71.4-84.1% of units in each represented month. Under exact
duplicate removal, that range remains 69.5-82.7%. This supports using order mix
alongside counts in planning, not treating every order as equal work.

Action: instrument small and large orders separately in a workflow pilot and
compare processing minutes and on-time completion before introducing separate
queues. Unit concentration is not a measured labor-hour share. January and
October are partial boundary months; one partial year cannot establish seasonality.

## 2. Compare Peak Responses

`response_comparison.csv` contains 18 simulations: retained/deduplicated demand,
30/40/50 assumed units per productive hour, and carryover/overtime/temporary
coverage. `response_daily.csv` preserves every capacity and queue calculation.

At 40 units/hour with retained demand:

| Policy | Backlog unit-days | Oldest queue age | Extra paid hours |
| --- | ---: | ---: | ---: |
| Carryover | 93,937 | 4 days | 0 |
| Overtime | 39,504 | 2 days | 732 |
| Temporary shifts | 71,296 | 4 days | 224 |

Overtime reduces accumulated queue burden by about 58% in this specific model;
the temporary policy reduces it by about 24%, but leaves maximum age unchanged.
These policies have different triggers, hours and assumed productivity, so this
is not evidence that overtime is inherently better than temporary workers.

Action: use this comparison to define a response-time versus extra-hours tradeoff.
Obtain measured throughput, customer deadlines, premium rates, agency lead times
and shift constraints before choosing a staffing policy or calculating savings.

All cases assume six workers, eight paid hours, 85% productive time, Monday-Friday
operation and zero initial backlog. Overtime adds two hours per worker when
opening backlog plus today's arrivals exceed base capacity. Temporary coverage
adds two eight-hour shifts at 80% productivity when the previous calendar day's
closing backlog exceeds one base day's capacity. Next-day worker availability
is assumed, not observed. Daily arrivals are known before processing; missing
dates and a 14-calendar-day recovery tail assume zero arrivals. FIFO units may
split orders. There are no measured deadlines, costs, fatigue or legal constraints.

## 3. Prioritize Location Review

`slotting_review_shortlist.csv` ranks 30 reference-size combinations and includes
retained/deduplicated demand, independent pick-file units, location counts and
monthly reference-level top-10 frequency. `monthly_top_references.csv` records
the monthly ranking; no future ranking is presented as a forecast.

Reference 8N10W9 appears in the top 10 in every represented month. Its sizes 11
and 10 lead the retained reference-size shortlist, with 2,951 and 2,931 units.
Those combinations appear at six and eleven pick-file locations respectively.
Multiple locations may be intentional reserve/forward storage, not inefficiency.

The location table lacks 22 codes representing 23,609 pick units (11.0%).
`unmatched_locations.csv` prioritizes their review. RC-01 and other unmatched
codes may represent staging or special locations; do not invent coordinates.

Action: reconcile these codes, then inspect access, replenishment and travel for
the high-volume shortlist. No move or travel-saving claim is justified yet.
Size labels are normalized numerically, not corrected or reinterpreted; unusual
source size encodings need a dictionary. Pick records are not treated as matched
order completions or a current stock-location snapshot.

## 4. Use an Item-Sensitive Packing Reference

`experimental_packing_reference.csv` shows the existing OpenPack S1 fixed-plus-item
fit for 1-5 items alongside observed medians, sample sizes and a constant estimate.
The implementation rejects other item counts. It is not applied to footwear
orders, which have no observed cartonization or matched packing workflow.

The exploratory equation is `66.984 + 13.067 * items` station seconds. Earlier
person-held-out evaluation reduced mean absolute error from 19.409 to 15.589
seconds. See `OPENPACK_TIMING_EVALUATION.md` for eligibility and evaluation.

Action: retain fixed handling plus item-dependent work in the model structure;
collect actual package counts, item counts and packing start/end times to fit a
site-specific version. Picking, breaks and incident allowances must be separate.
Screened experimental timing cannot establish paid-hour productivity targets.

## 5. Audit Duplicates Before Staffing Claims

`duplicate_rows_for_review.csv` identifies 2,559 repeated rows and 12,735 units
using original CSV line numbers. Totals are 228,195 retained versus 215,460 after
exact duplicate removal. There are also 33 zero-quantity and 16 missing-size rows.

The source README does not establish a unique row identifier or prove that
repetitions are extraction errors. Example: PY5UPB size 260 has 2,340 retained
order units, 535 after deduplication, and 2,338 independent pick-file units.
That is a warning against deleting repetitions, not proof of one-to-one matching.

Action completed: preserved raw records, generated a review file, and reran all
response cases and monthly segmentation under both interpretations. The final
duplicate classification remains unresolved. To resolve it, obtain the source
extract query, unique WMS line key and meaning of `orderToCollect`, or document
both bases permanently as a public-data limitation. Similar aggregate totals
between orders and picks do not establish record-level reconciliation.

## Reproduction and Sources

```bash
python3 scripts/analyze_operational_actions.py --locations '/path/to/Storage_Location.csv'
PYTHONPATH=src python3 -m unittest discover -s tests
```

`audit_and_assumptions.json` contains source SHA-256 fingerprints and all policy
assumptions. The location file comes from the user's original downloaded dataset.

Footwear data: Rodrigo Furlan de Assis, *Order Picking Dataset from a Warehouse
of a Footwear Manufacturing Company*, version 1, DOI 10.17632/pf2w725pw3.1,
CC BY 4.0. Outputs are transformed analyses, not endorsed source findings.
OpenPack: Zenodo record 8145223, CC BY-NC-SA 4.0; experimental portfolio use.
