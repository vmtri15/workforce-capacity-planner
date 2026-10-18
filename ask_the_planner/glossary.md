## Cases and runs
- The database holds three planning runs: low, base and high productivity. They use the same demand and the same staff. Only the work speed changes.
- "Base case", or any question that does not name a case, means the base run: planning_runs.productivity_case = 'base', run_id = 'base_demand_base_productivity'.
- "Low case" and "high case" mean productivity_case = 'low' and 'high'.

## Sites and roles
- Three sites: joliet (Joliet/Elwood), ohare (O'Hare area), kenosha (Kenosha/Pleasant Prairie). Use site_id in joins and site_name when showing names.
- "Share of demand" for a site is sites.allocation_share.
- Four roles: fulfillment_associate (picking), packing_associate, warehouse_supervisor, shipping_receiving_coordinator.
- "Direct roles" are the fulfillment and packing associates (roles.direct_capacity_role = 1). Only direct roles have daily capacity results. Supervisors and coordinators are paid and counted as staff but have no capacity results.

## Staff and cost
- "Workers", "staff", "headcount" and "positions" mean staffing_plans.scheduled_headcount. A total across roles counts all four roles. Headcount is the same in all three runs.
- "Daily staffing cost" for a site is the sum of scheduled_headcount * paid_hours_per_person * median_hourly_wage over its roles in staffing_plans.
- "Total staffing cost" over the planning window means all roles for all days: planning_run_summary.all_role_scheduled_wage_cost. "Direct labor cost" is only the direct roles: planning_run_summary.direct_scheduled_wage_cost, which equals the sum of daily_capacity_results.scheduled_wage_cost.
- "Hourly wage" or "pay" means median_hourly_wage. Wages for a site come from staffing_plans. The wider wage benchmarks by area are in wage_benchmarks.
- "Productive hours per worker per shift" is paid_hours_per_shift times productive_time_factor. Both are in scenario_assumptions.

## Capacity and service
- "Shortfall hours" or "capacity gap" means daily_capacity_results.capacity_gap_hours: the hours of work that day that the scheduled direct staff could not cover. A total is the sum of that column.
- "Idle hours" or "spare capacity" means daily_capacity_results.surplus_hours.
- "Coverage" is the share of a day's workload the staff can complete: daily_capacity_results.coverage_rate.
- The "service target" is 95% of the day's workload (scenario_assumptions.service_target). A site role day meets the target when service_target_met = 1.
- "On time rate", "service rate" or "share of days meeting the target" means the share of site role days that met the target: AVG(service_target_met) from daily_capacity_results. For a whole run this is planning_run_summary.role_site_day_service_rate.
- A site "misses a day" when at least one direct role at that site has service_target_met = 0 on that date.
- The "worst day" is the site role day with the largest capacity_gap_hours.

## Demand
- "Planned demand" is the modeled workload: modeled_daily_workload (modeled_orders, modeled_order_lines, modeled_units). It is the original data multiplied by the demand scale, which is 5 (scenario_assumptions.demand_scale), and split across the sites. A total across all sites for a day is the sum over the three sites.
- "Original demand" or "observed demand" is workload_daily_source: distinct_invoice_ids are orders, positive_quantity_lines are order lines, positive_units are units.
- The planning window is 56 calendar days, 2011-10-14 to 2011-12-08. The source has records on 48 of those days. The other 8 days have no records and are planned as zero demand.
- The "busiest day" is the date with the largest total modeled_units across all sites.
- "Orders per day on average" divides by all 56 calendar days, including the 8 days with no records, unless the question says recorded days only.

## What this data is and is not
- The demand is a retail order history from 2011, scaled up and used as a stand in. It is not data from a company that runs these sites.
- Wages are May 2025 benchmark wages. Productivity rates are assumptions, not measurements. The quality of every number depends on those assumptions.
- The database has no 2023 data, no actual staffing records, no costs of overtime or temporary workers, and no hiring recommendations. A question about those cannot be answered from it.
- source_registry.evidence_class says whether a source is observed, reference or assumption. scenario_assumptions.classification does the same for each assumption.
- qwi_labor_flows holds Census labor data by county and quarter: hires, separations and employment for warehousing (naics_code 493).
