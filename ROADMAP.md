# Project Roadmap

## Phase 1 Research and feasibility

- Completed: initial domain screening and selection of the Illinois–Wisconsin study corridor.
- Completed: downloaded and compared 2025 Q4 QCEW warehousing/courier benchmarks.
- Completed: compared parcel sortation with fulfillment/distribution for public-data fit; selected outbound fulfillment/distribution, beginning with picking and packing.
- Completed: verified Census QWI API access, Census CBP API access, county geography, and BLS QCEW coverage; documented the available data limits.
- Completed: researched the four initial roles, O*NET mappings, wage-benchmark geography, workflow boundaries, and workload provenance.
- Completed: finalized the observed/estimated/assumed input register and workload-transformation design.
- Completed: saved May 2025 OEWS role-specific wage extracts for Chicago and Kenosha.
- Completed: converted the historical UCI source into a reproducible 604-day daily workload profile; exact repeated rows across the December 2010 sheet overlap were removed.
- Completed: selected an order-lines-per-productive-hour measure and documented a source-informed, explicitly uncalibrated low/base/high sensitivity range.
- Completed: set the first model's planning horizon, shift rules, service target, site-allocation rule, productivity cases, and initial active staffing as visible assumptions.
- Phase 1 gate status: complete for a prototype with explicit evidence limitations. Calibration remains a future validation requirement.

## Phase 2A Build the data foundation — after research gate

- Completed: created the SQLite schema and reproducible ingestion job for workload, wages, Census CBP, and BLS QCEW.
- Completed: added source metadata, evidence limitations, foreign keys, and nine build-time data-quality checks.
- Completed: stored explicitly classified prototype assumptions separately from observed source tables.
- Completed: refreshed Census QWI to 80 county-quarter records covering 2021 Q1 through 2025 Q4 for hiring and separation context.
- Phase 2A status: complete. The database rebuild passes all 11 data-quality checks.

## Phase 2B Build the planning engine

- Completed: created a deterministic 56-day modeled workload for all three sites while retaining source-date traceability.
- Completed: represented the eight dates absent from the source as explicit zero-demand calendar dates.
- Completed: held the agreed 69-position staffing plan and modeled demand constant across low, base, and high productivity cases.
- Completed: calculated required labor hours, effective productive capacity, workload coverage, wage cost, and capacity gaps for picking and packing.
- Completed: added eight planning-engine quality checks covering row completeness, allocation reconciliation, fixed staffing, and scenario ordering.
- Phase 2B status: complete for the historical-pattern prototype. The output is scenario analysis, not a future statistical forecast; forecast validation requires newer operational demand data.

## Phase 3 Build scenarios and optimization

- Completed Phase 3A: researched overtime and temporary-worker constraints; implemented 24 preliminary single-action comparisons across productivity cases and 95%/100% completion targets. See `STAFFING_OPTIONS_RESEARCH.md`.
- Completed Phase 3B: configurable policy, synthetic weekly roster, finite temporary pools with readiness gates, and CP-SAT optimization of overtime plus temporary shifts. Six scenarios and twelve unit tests validate feasibility limits; see `PHASE_3B_RESULTS.md`.
- Completed Phase 3C: paid cross-training, synthetic cross-role eligibility, fixed-term hiring with paid onboarding and guaranteed schedules, and transfers with donor capacity/travel accounting. The joint optimizer preserves feasibility versus proven optimality and tests slower travel. See `PHASE_3C_RESULTS.md`.
- Phase 3C verification closed September 15, 2026: all 25 tests passed; six scenarios regenerated, with four audited feasible/optimal plans and two infeasible cases. The standard low-productivity plan remains FEASIBLE, not proven optimal. Backlog and dated absences remain outside Phase 3C.
- Completed research follow-up: reviewed three packing sources and specified a package-plus-unit workload extension in `PACKING_RESEARCH.md`.
- Completed: candidate outbound audit reconciled all 604 source days; implemented and tested a standalone package-plus-unit packing calculation and diagnostic. See `OUTBOUND_AUDIT_RESULTS.md`.
- Completed: reviewed nonstandard codes, retained unresolved rows in a review register, and generated three individual-unit packing-job sensitivities. All 19 focused tests pass; see `PACKING_SCENARIO_DECISION.md`.
- Completed: opt-in productive-hour packing demand interface, three separate sensitivity runs, and dashboard workload-model selection. All three packing scenarios are infeasible under unchanged staffing/action limits; see `PACKING_INTEGRATION_RESULTS.md`. Rates remain uncalibrated.
- Remaining: carryover backlog, dated absences and broader disruption handling. Daily synthetic schedules do not establish intraday operational or payroll compliance.

## Phase 4 Build the product

- Completed portfolio scope: observed-demand overview, side-by-side scenario
  comparison, downloadable comparison results, validated recommendations,
  methodology/evidence boundaries, and embedded Tableau Public analysis.
- Completed: rebuilt the site-level network capacity replay around retained
  2023 demand, with modeled allocation across three sites, fixed staffing sized
  from recorded workload, and low/base/high productivity sensitivities.
- Completed: reconciled site-level capacity, later-period policy validation,
  all-policy replacement search, refreshed QWI through 2025 Q4, and external
  process-timing context into a direct conditional answer in `DECISION_ANSWER.md`.
- Completed deployment packaging: API-free static data bundle and GitHub Pages
  workflow. A public site still requires connecting this checkout to a GitHub
  repository and enabling Pages.
- Deferred beyond the portfolio prototype: authentication, saved scenarios,
  approvals, decision history, and forecast-versus-actual workflows.

## Phase 5 Validate

- Test normal demand, demand spike, absence spike, hiring delay, skill shortage, weather disruption, and hub closure.
- Compare against simple staffing rules.
- Measure forecast error, capacity coverage, cost, service level, overtime, and usability.

## Phase 6 Package the portfolio project

- Ready to deploy: static dashboard artifact and GitHub Pages workflow.
- Completed: technical README and product architecture diagram.
- Completed: defensible recommendations and evidence limitations in the web
  methodology and recommendation views.
- Remaining after deployment: record a three-to-five-minute demo video and add
  the public URL plus final screenshots to the README.
