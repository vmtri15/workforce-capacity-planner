# Workforce Capacity Planner for Distributed Operations

## Project purpose

Build a decision-support product that helps operations and recruiting teams determine whether they have enough skilled labor to complete forecasted workload, then compare practical responses when a capacity gap appears.

The product connects demand forecasting, workforce capacity, recruiting pipeline data, labor-market information, and scenario optimization.

## Starting scenario

A modeled e-commerce/logistics operator plans workforce capacity across the Chicago–southeast Wisconsin corridor: Joliet/Elwood, the O’Hare-area cluster, and Kenosha/Pleasant Prairie. These are researched study areas, not verified company facilities. See SCENARIO.md for evidence and boundaries.

Current stage: Phase 1 — research and feasibility. The next decision is a consistent facility type (parcel sortation or fulfillment/distribution), selected on data and operational evidence. The call-center direction is superseded.

## Core user question

Can each location complete the expected workload with the available workforce, and what is the least risky and most affordable action if it cannot?

## Target users

- Operations manager
- Recruiting or staffing manager
- Workforce planner or executive

## Core workflow

1. Import workload, workforce, recruiting, and external data.
2. Forecast demand by location and time period.
3. Convert demand into required labor hours.
4. Calculate effective capacity from worker availability, skills, productivity, and attendance.
5. Identify location, role, shift, and skill gaps.
6. Test hiring, training, overtime, transfer, and temporary-worker scenarios.
7. Recommend an action with visible assumptions and tradeoffs.
8. Track actual results against the forecast and recommendation.

## Differentiation

Do not present this as a generic workforce-management or scheduling platform. The project focuses on the connection between recruiting capacity and operational workload: how many qualified people must be available, by when, and what happens if hiring or training is delayed.

## Team fit

Tri Vi: business analytics, Python, SQL, forecasting, optimization, operations, dashboards, APIs, backend, and deployment.

Partner: international business, HR and staffing, talent sourcing, interviewing, communication, project coordination, recruiting workflow, product requirements, and data validation.

Both partners contribute to data analysis, product decisions, and testing.

## Data approach

Use verified public data for regional labor benchmarks and operational context. Test candidate APIs before claiming integration. Facility workload, workforce records, skills, absences, and recruiting pipelines require either direct evidence or explicitly documented simulation; no private Shopee data is required. Public employment counts do not supply parcel volumes or available applicants.

## Initial scope

- One region spanning Illinois and Wisconsin; three modeled site areas.
- One consistent facility type, still under research.
- Roles, headcount, shifts, planning horizon, and productivity selected after evidence review.
- One baseline forecast and one comparison model where observed workload supports evaluation.
- Staffing scenarios covering demand, absence, skills, hiring delays, and disruption.
- Dashboard separating observed inputs, assumptions, forecasts, and simulated results.

## Technology direction

Python, FastAPI, PostgreSQL/PostGIS, Pandas or Polars, Scikit-learn or XGBoost, OR-Tools, Streamlit for the first usable prototype, and later Next.js/TypeScript if a polished product interface is needed.

## Evidence standards

Label sourced data, simulated data, assumptions, forecasts, and actual outcomes separately. Use chronological holdouts for forecasting. Do not claim real-world savings from simulated data. Show the assumptions behind every recommendation.

All material choices require data, benchmarks, or cited research. Label evidence gaps explicitly rather than replacing them with undocumented defaults.
