# Regional Logistics Workforce Capacity Planning Scenario

## Status and selected direction

Updated 2026-09-12. Current stage: Phase 1 — research and feasibility.

Workforce Capacity Planner for Distributed Operations in e-commerce/logistics. The call-center scenario is superseded. The approved initial study region is the Chicago–southeast Wisconsin logistics corridor. These are three study areas for modeled facilities.

Selected operating model: e-commerce fulfillment/distribution, beginning with
outbound picking and packing. Parcel sortation was screened but not selected
because the public data found so far does not connect its workload to
worker-level labor time as clearly. All three sites are modeled study areas,
not identified facilities.

## Selected study areas

| Study area | Public-data geography | Research basis |
|---|---|---|
| Joliet/Elwood, Illinois | Will County, FIPS 17197 | Substantial warehousing employment and documented BNSF/Union Pacific intermodal infrastructure. |
| O’Hare-area logistics cluster, Illinois | Cook (17031) and DuPage (17043) counties as broad benchmarks | Documented freight cluster and truck-route planning; broad employment base. |
| Kenosha/Pleasant Prairie, Wisconsin | Kenosha County, FIPS 55059 | Distribution activity on the I-94 corridor and a second-state labor-market comparison. |

Cook and DuPage totals are not O’Hare employment. County jobs are not available applicants, individual facility headcounts, or parcel throughput. Exact addresses and labor catchments remain unselected.

## Verified regional benchmarks

Downloaded BLS QCEW 2025 Q4 industry CSVs on 2026-09-12. Private ownership (own_code=5), all establishment sizes; employment is December 2025 (month3_emplvl). The listed employment values are disclosed, not suppressed zeros. This is a fixed historical comparison, not a claim about current employment or the latest release.

| County | Warehousing/storage jobs, NAICS 493 | Courier/messenger jobs, NAICS 492 |
|---|---:|---:|
| Will, IL | 28,283 | 3,555 |
| Cook, IL | 18,339 | 30,029 |
| DuPage, IL | 9,403 | 6,015 |
| Kenosha, WI | 9,678 | 570 |

Alternative warehousing benchmarks using the same period and definition: Allen County/Fort Wayne 2,162; Marion County/Indianapolis 8,201; Hendricks County 12,724; Boone County 14,517; Franklin County/Columbus 19,287. Indianapolis remains a credible alternative; Marion alone understates its surrounding warehouse market. The chosen corridor narrows the initial geographic scope while retaining two states and documented logistics clusters. No numerical site-selection score or claim of globally optimal locations is implied.

NAICS 493 and 492 are different industries. Select the relevant benchmark after defining the facility type; do not treat broad industry employment as evidence of a particular SOC’s capacity.

## Business situation and decision

A modeled logistics operator must plan enough qualified labor to process forecast workload at three sites by operational cutoffs. Workload, absences, skills, and recruiting delays can create gaps. The product compares feasible responses and explains their cost, timing, and service consequences.

Core question: Can each site meet its workload and cutoff with available skilled labor, and should a gap be addressed by changing coverage, overtime, temporary labor, training, or hiring?

## Proposed users

- Operations manager/supervisor: identify workload gaps and compare operating responses.
- Workforce planner: forecast workload, estimate effective capacity, and plan coverage.
- Recruiting/staffing coordinator: assess persistent gaps, required start dates, and training delays.

These are product personas. Actual modeled production roles and leadership requirements must be researched.

## Data and API plan

| Input | Candidate source and access | Verification and limits |
|---|---|---|
| Regional employment and industry wages | BLS QCEW downloadable CSV endpoints | 2025 Q4 NAICS 492/493 files downloaded and compared. Industry-average wages are not role-specific wage rates. |
| Occupational tasks and skills | Local O*NET Database 31.0 download | Four production and support roles mapped in `../research/ROLE_RESEARCH.md`; tasks/skills do not set wage or productivity values. |
| Hiring, separations, earnings | Census QWI API | Documentation identified; test selected geographies/industries and suppression before adoption. Aggregate flows do not provide a company recruiting pipeline or time-to-hire. |
| Role-specific wages | BLS OEWS occupational wage tables | OEWS geography is now mapped in `../research/LABOR_MARKET_RESEARCH.md`; retain each saved extract's release year and SOC coding. |
| Workload patterns | UCI Online Retail II; LaDe as an alternative last-mile source | UCI ZIP and a LaDe CSV sample were accessed. Neither supplies actual workload at the selected US sites. Retail transactions are not SOC arrivals; LaDe is last-mile activity, not internal sorting. |
| Weather | Open-Meteo historical API | Documentation identified; not yet integrated. Use only if dates/geography align and an operational use is justified. |
| Facility roster and hiring pipeline | Reproducible simulation or editable scenario inputs | No private company data is required or available. |

A critical feasibility gap remains: a defensible workload source or explicitly simulated workload process for the selected facility type. Do not relabel UK retail or Chinese courier data as observed Illinois/Wisconsin operations. Any adaptation must be documented and evaluated as a scenario.

## Scope and assumptions

- Three modeled facilities in the selected study areas, all using outbound fulfillment/distribution processes.
- Production roles are fulfillment associate, packing associate, shipping/receiving coordinator, and warehouse supervisor. Workforce counts, shifts, productivity, training times, costs, planning horizon, and service targets remain open research inputs.
- Use public data for context and benchmarks; clearly label simulated workload, workforce, absences, skills, and recruiting stages.
- Forecasts, observed historical outcomes, and simulated policy outcomes must be displayed separately.
- No assumption of convenient same-day staff sharing across the corridor. Transfers require addresses, travel time/cost, worker availability, skill compatibility, and protection of the sending site’s service.
- No unsupported three-role limit, fixed headcount, 12-week horizon, or default productivity rate.

## Scenario framework

| Scenario | Change | Decision and output |
|---|---|---|
| Baseline | Researched workload pattern and stated availability assumptions | Required labor, effective capacity, gaps, cost, and cutoff performance by site. |
| Demand surge | Explicit sensitivity range after workload profiling | Compare revised coverage, overtime, and temporary staffing. |
| Absence spike | Reduced available labor | Identify bottlenecks and feasible recovery without double-counting labor. |
| Skill shortage | Insufficient qualified people in one process | Compare training, qualified temporary staff, and hiring with readiness delays. |
| Persistent gap | Sustained shortage over the selected planning horizon | Compare recurring overtime with hiring cohorts and onboarding costs. |
| Hiring/training delay | Planned hires become productive later | Show interim coverage, unmet workload, and recovery dates. |
| Site disruption | Reduced site capacity | Evaluate rerouting workload or transfers only where operational compatibility and travel constraints are supported. |

Shock magnitudes and constraints are not yet set. These scenarios define questions, not researched event probabilities or promised savings.

## Validation

Compare a simple staffing baseline with proposed plans under consistent demand and absence realizations. Evaluate forecast accuracy only against genuine held-out observations. Evaluate staffing interventions through clearly labeled simulation, including uncertainty and infeasible cases. Report workload coverage, cutoff service, labor hours, overtime, and assumed costs. Do not infer real savings from simulated outcomes.

## Next research gate

Complete the workload-to-capacity evidence before implementation:

1. Save OEWS wage extracts for the four roles and the Chicago/Kenosha benchmark areas.
2. Define a data dictionary that separates observed source fields from estimated and assumed inputs.
3. Document the workload transformation from the historical retail/order datasets to modeled fulfillment demand.
4. Set low/base/high productivity assumptions, explicitly marked uncalibrated until a source with labor-time fields is found.
5. Then define headcount, shifts, capacity formulas, service targets, and scenario ranges.

## Sources

- [BLS QCEW open-data documentation](https://www.bls.gov/cew/additional-resources/open-data/home.htm)
- [BLS 2025 Q4 warehousing CSV](https://data.bls.gov/cew/data/api/2025/4/industry/493.csv)
- [BLS 2025 Q4 courier CSV](https://data.bls.gov/cew/data/api/2025/4/industry/492.csv)
- [Will County transportation assets](https://willcountyced.com/site-selection/transportation-assets/)
- [CMAP freight clusters and truck bottlenecks](https://cmap.illinois.gov/regional-plan/resources/maps/local-freight-clusters-and-truck-bottlenecks/)
- [Kenosha distribution/logistics profile](https://www.kaba.org/industries/transporation-logistics/)
- [O*NET API](https://services.onetcenter.org/)
- [Census QWI API](https://www.census.gov/data/developers/data-sets/qwi.html)
- [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- [LaDe](https://cainiaoai.github.io/LaDe-website/)
- [Open-Meteo historical weather API](https://open-meteo.com/en/docs/historical-weather-api)
