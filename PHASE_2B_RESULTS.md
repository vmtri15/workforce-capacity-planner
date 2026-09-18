# Phase 2B Planning Engine Results

## What the engine answers

The prototype tests whether one fixed daily staffing plan can cover the same
modeled eight-week workload under low, base, and high productivity. It uses the
historical UCI order pattern, scales it by 5x, and allocates it across the three
modeled sites using the documented QCEW proxy shares.

This is a deterministic scenario comparison. It is not a claim about future
demand and is not a validated statistical forecast.

## Fixed staffing plan

All three cases use 69 active daily positions: 54 fulfillment associates, six
packing associates, six supervisors, and three shipping/receiving
coordinators. Holding staffing and workload constant isolates the effect of the
productivity assumption.

## Results

| Productivity case | Total gap hours | Direct role-site-days meeting 95% target | Scheduled wage cost, direct roles | Scheduled wage cost, all four roles |
| --- | ---: | ---: | ---: | ---: |
| Low | 999.5 | 90.2% | $507,620 | $628,598 |
| Base | 113.3 | 98.2% | $507,620 | $628,598 |
| High | 0.0 | 100.0% | $507,620 | $628,598 |

The base case misses the target only for fulfillment associates on two peak
dates at each site. Packing has no modeled shortage in any case because the
minimum one-packer-per-shift rule provides more capacity than this workload
requires. The low case produces picking shortages at every site; the high case
covers all modeled picking and packing work.

The wage cost is the same in all three cases because this phase holds scheduled
headcount fixed. Direct cost includes fulfillment and packing roles. The
all-role figure also includes supervisors and coordinators. It excludes payroll
taxes, benefits, overtime premiums, absence coverage, and agency markups.

## Data checks

The run contains three planning cases, 56 dates per case, three sites, and two
direct-capacity roles. All eight engine checks pass. They confirm that site
allocations preserve each daily source total, staffing is identical across
cases, zero-source dates are explicit, and gap hours decline as productivity
increases.

## Decision implication

The fixed plan is reasonably robust at the 60-lines-per-hour base assumption,
but the remaining 113.3 picking gap hours are concentrated on peak dates. Phase
3 should compare targeted overtime, temporary labor, cross-training, and extra
scheduled headcount instead of raising every site's baseline staffing for all
56 days.

The productivity rates remain uncalibrated public benchmarks. A real deployment
must replace them with local measured standards and use newer order data before
staffing decisions are made.

## Reproduce

```bash
python3 scripts/build_database.py
python3 scripts/run_planning_engine.py
sqlite3 -header -column data/workforce_planner.db "SELECT * FROM planning_run_summary ORDER BY productivity_case;"
```
