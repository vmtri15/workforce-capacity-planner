# Footwear Demand and Backlog Experiment

Status: **uncalibrated portfolio scenario**, separate from the existing database,
dashboard and optimizer. This is a deterministic simulation, not a staffing
recommendation or forecast.

## Source and Boundaries

Customer_Order.csv from Rodrigo Furlan de Assis, *Order Picking Dataset from a
Warehouse of a Footwear Manufacturing Company*, version 1,
DOI 10.17632/pf2w725pw3.1, CC BY 4.0. Daily aggregation is a transformation of
the source. The generated JSON records the input SHA-256 fingerprint.

- 122,370 source rows, 228,195 units, 178 dates from January 5 to October 19, 2023.
- All rows retained, including duplicates and 33 zero-quantity rows. The latter
  contribute zero units; negative quantities cause a validation error.
- Creation dates serve as arrival proxies, not measured picking dates.
- Picking_Wave.csv is not treated as matched completion history.
- No employee-level joins to Kaggle, OpenPack, or JTH. The Kaggle absence file
  is not used here; these absences are explicitly constructed scenario inputs.

## Assumed Policy

One hypothetical site, six workers, Monday-Friday shifts, eight paid hours,
85% productive time, and 40 units per productive hour. None is calibrated to
this warehouse. Initial backlog is zero. Missing source dates mean assumed zero
arrivals, not verified zero demand. All daily arrivals are available before
processing; time-of-day and partial-order shipping constraints are ignored.

The stress case removes two fictional workers for five weekdays beginning
March 22, the busiest source weekday. Selecting the peak retrospectively is
a stress-test design, not a predictive result. Fourteen extra calendar days
with zero arrivals are appended for recovery; capacity is never banked.

FIFO processing carries unfinished units to later dates. Each date satisfies:
`opening backlog + arrivals = completed + closing backlog`.
Age measures calendar days since the oldest unfinished arrival, not an SLA.

## Saved Results

| Metric | No absences | Synthetic peak absences |
| --- | ---: | ---: |
| Arrivals | 228,195 | 228,195 |
| Modeled completed units | 228,195 | 228,195 |
| Peak closing backlog | 4,279 | 4,823 |
| Maximum oldest-backlog age (days) | 4 | 6 |
| Backlog unit-days | 93,937 | 110,936 |
| Ending backlog after recovery window | 0 | 0 |

Backlog unit-days sum daily closing backlog, representing accumulated queue
burden, not exact individual waiting time. The synthetic absences remove 2,720
units of assumed capacity. These differences are scenario outputs, not measured
business impact. Finishing the queue does not establish on-time service.

## Reproduce

From the project directory, using Python 3:

```bash
python3 scripts/build_footwear_scenario.py
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_backlog.py'
```

Output: `data/processed/footwear_backlog_scenario.json`, including daily inputs,
capacity, completions, queue size, source-presence flags and evidence caveats.
Next integration: a separately labeled dashboard comparison of these two cases;
do not replace the original planning baseline or display them as optimized runs.
