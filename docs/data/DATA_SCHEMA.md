# Data Schema and Lineage

## Database build

`scripts/build_database.py` recreates `data/workforce_planner.db` from the
documented local inputs. It builds a temporary database, runs the input quality
checks, and replaces the prior database only after every check passes.

`scripts/run_planning_engine.py` then creates the three Phase 2B planning runs
and executes a separate set of planning-output checks.

## Observed and benchmark tables

| Table | Grain | Current rows | Purpose |
| --- | --- | ---: | --- |
| `source_registry` | One row per registered source | 5 | Source URL/path, release, access date, and limitation metadata |
| `workload_daily_source` | One observed UCI source date | 604 | Cleaned positive units, order lines, invoice IDs, and non-positive lines |
| `wage_benchmarks` | OEWS area and modeled role | 8 | May 2025 median hourly wage benchmarks |
| `regional_industry_benchmarks` | CBP county proxy | 4 | 2023 NAICS 493 establishments, employment, and payroll |
| `qcew_industry_benchmarks` | QCEW county proxy | 4 | 2025 Q4 NAICS 493 employment benchmarks used for site shares |
| `qwi_labor_flows` | County-quarter | 80 | 2021 Q1 through 2025 Q4 employment, hires, and separations context |

These tables store public observations or published benchmarks. County and
metro values are context proxies and do not describe an identified facility.

## Model configuration tables

| Table | Grain | Current rows | Purpose |
| --- | --- | ---: | --- |
| `sites` | Modeled site | 3 | Geography proxy, wage area, and editable demand-allocation share |
| `roles` | Modeled role | 4 | Workflow role and O*NET/OEWS mapping |
| `scenario_assumptions` | Named assumption | Varies | Numeric/text values with classification, unit, basis, and editability |

The configuration tables keep assumptions separate from observed source
records. `../product/MODEL_ASSUMPTIONS.md` explains the initial values and limitations.

## Phase 2B output tables

| Table or view | Grain | Current rows | Purpose |
| --- | --- | ---: | --- |
| `planning_runs` | Scenario run | 3 | Low, base, and high productivity case metadata |
| `staffing_plans` | Run-site-role | 36 | Fixed scheduled headcount, hours, wage, and staffing rule |
| `modeled_daily_workload` | Run-planning date-site | 504 | Scaled and allocated orders, lines, units, and pack jobs |
| `daily_capacity_results` | Run-date-site-direct role | 1,008 | Required hours, capacity, gap/surplus, coverage, service result, and direct wage cost |
| `planning_run_summary` | Scenario run | 3 | Headline workload, staffing, gap, service, and cost results |

`modeled_daily_workload.planning_date` covers all 56 calendar dates.
`source_date` is nullable so the eight dates absent from the UCI source remain
visible with `source_record_present = 0` and zero workload.

## Quality tables

`data_quality_results` stores the input build checks. They cover source row
counts, uniqueness, non-negative measures, site-share totals, role and wage
coverage, QWI completeness, and foreign keys.

`planning_quality_results` stores eight engine checks. They verify run and row
counts, the full calendar, fixed staffing across cases, preservation of daily
totals after site allocation, and the expected decline in gap hours from low to
high productivity.

Any failed planning check raises an error and rolls back the engine transaction.

## Key relationships

- Every modeled workload and capacity row belongs to a `planning_runs` record.
- Every staffing row references one modeled `sites` and `roles` record.
- Every capacity result references the matching run-date-site workload and the
  matching run-site-role staffing plan.
- A non-null modeled `source_date` references `workload_daily_source`.
- Wage and labor-market tables reference their registered source metadata.

SQLite foreign keys are enabled in both build and planning scripts.

## Phase 3B artifacts

The optimizer reads the planning database without modifying its tables.
`config/optimization.json` records editable synthetic policies.
`data/processed/optimization_results.json` records the synthetic roster, dated
actions, readiness dates, policy snapshots, solver statuses, daily capacity,
incremental costs, OR-Tools version and source database fingerprint. Infeasible
scenarios have no overall cost; any solved groups are partial diagnostics.
Re-run the optimizer after changing the database or configuration.

## Phase 3C artifacts

`config/workforce_actions.json` adds synthetic training, hiring and transfer
controls. `data/processed/network_optimization_results.json` stores the joint
network solutions, eligibility records, paid hiring schedules, training and
travel time, action costs, reconstructed capacity, solver statuses and cost
bounds. It includes the database and network-optimizer implementation hashes.
There are six scenarios, including four-hour transfer travel. An INFEASIBLE or
UNKNOWN run has no total cost or action recommendation. See `../validation/PHASE_3C_RESULTS.md`.

## Rebuild sequence

```bash
python3 scripts/build_database.py
python3 scripts/run_planning_engine.py
```

The database is generated output and is excluded from version control. The SQL
schema, ingestion scripts, processed input files, and documentation are the
reproducible source of truth.
