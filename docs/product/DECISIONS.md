# Decision Log

## 2026-09-12

- Chosen project: Workforce Capacity Planner for Distributed Operations.
- Starting domain: e-commerce fulfillment.
- Product focus: connect recruiting capacity with operational workload; do not recreate a generic employee scheduling platform.
- Data approach: hybrid public and simulated data.
- MVP interface: Streamlit first; consider Next.js after the planning logic is stable.
- Recommendation transparency: every result must identify its assumptions and whether values are sourced, simulated, forecasted, or actual.
- No claim of literal market novelty. Differentiation will come from the specific workflow, integration of recruiting and operations, explainability, and evaluation.

## 2026-09-12 — revised direction after data research

- Supersedes the initial specific fulfillment scope and subsequent call-center scenario: return to regional e-commerce/logistics workforce planning.
- Approved study corridor: Chicago–southeast Wisconsin, with Joliet/Elwood, O’Hare-area logistics cluster, and Kenosha/Pleasant Prairie as modeled site areas.
- Regional choice is supported by downloaded BLS 2025 Q4 NAICS 492/493 data and logistics infrastructure sources in SCENARIO.md. Exact sites and capacity are not verified.
- Selected operating model: e-commerce fulfillment/distribution with outbound picking and packing. Parcel sortation was screened but not selected because the public data found so far does not connect workload to worker-level labor time as clearly.
- Initial production/support roles: fulfillment associate, packing associate, shipping/receiving coordinator, and warehouse supervisor. Detailed mapping is in `../research/ROLE_RESEARCH.md`.
- Research first: data availability, benchmarking, and sources must precede location, role, headcount, productivity, and scenario decisions.
- Current phase is research and feasibility, not implementation. 
- Public regional data supports context, not actual site workload or hiring pipelines. Label simulation and geographic adaptations explicitly.

## 2026-09-13 — initial model specification

- First model grain: daily capacity across the source-derived peak eight-week window, 2011-10-14 through 2011-12-08.
- Initial workload scale: 5x the cleaned source pattern; this is an editable scenario input, not observed local demand.
- Initial site shares: 43% Joliet/Elwood, 42% O'Hare area, and 15% Kenosha/Pleasant Prairie, based on rounded relative 2025 Q4 QCEW NAICS 493 employment.
- Initial operation: two eight-hour shifts with an 85% productive-time factor and a 95% same-day workload target. All are visible assumptions.
- Base productivity: 60 pick lines per productive hour and 50 pack jobs per productive hour; both remain source-informed and uncalibrated.
- Initial active daily staffing: 69 positions across the three sites. This is a calculated scenario output, not a claim about actual facilities or payroll headcount.
