# Packing-time reference evaluation

## Method

Reproduce with `python scripts/evaluate_openpack_timing.py` after the timing audit.
Target: annotated packing-station work excluding the operation labeled Picking.
Eligibility: audit screen passes, no elapsed gap above 1 ms, and 1-5 items.
1,526 boxes qualify. Incident/gap exclusions can favor easier work; these are
reference observations, not representative production labor standards.

Two estimates are compared: a training-set mean seconds/box and ordinary least
squares `seconds = intercept + slope * item_count`. Each experimental scenario
is evaluated separately. For each fold, all observations from one distinct person
are excluded from fitting and used for evaluation. Repeat recording IDs have
already been mapped to the same person. No demographics or individual identity
are used as predictive features.

## Results

Mean absolute error in seconds, averaged equally across held-out people:

| Scenario | Eligible boxes | People | Constant estimate | Item-count estimate |
| --- | ---: | ---: | ---: | ---: |
| S1 standard procedure | 791 | 11 | 19.409 | 15.589 |
| S2 flexible procedure | 286 | 10 | 15.431 | 13.188 |
| S3 irregular/preassembled-box conditions | 304 | 10 | 15.017 | 11.901 |
| S4 time pressure | 145 | 10 | 13.230 | 8.388 |

S1's exploratory full-sample equation is `66.984 + 13.067 * items` seconds.
It describes the selected experimental station operations, not paid hours,
warehouse picking routes, or a measured footwear packing rate. It is not a
replacement for the earlier thesis-derived task-time assumptions: the operation
definitions and order mix differ.

The screened S1 mean is 90.260 seconds versus 93.753 across all S1 records.
This difference is descriptive and does not isolate an incident effect.
Box size and work location can confound the item-count relationship. Scenario
differences do not establish causal productivity improvements.

## Portfolio decision

Use S1 as the first candidate for a separately labeled experimental small-order
reference, restricted to 1-5 items and the documented workflow. S2-S4 are separate
sensitivity contexts, not selectable worker performance targets. Do not extend
the fitted equation to the 12/24/48-unit jobs in the current optimizer or silently
replace those assumptions. A future scenario must account explicitly for omitted
picking, breaks, incident work and uncertainty, with a final independent test if
predictive performance is claimed.

Outputs: `data/processed/openpack_timing_evaluation.json` includes item-count and
person summaries, fold errors and source hash. `openpack_held_out_predictions.csv`
contains per-box held-out predictions for verification. Optimizer inputs unchanged.

Source: OpenPack https://zenodo.org/records/8145223, CC BY-NC-SA 4.0.
