PRAGMA foreign_keys = ON;

CREATE TABLE source_registry (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    publisher TEXT NOT NULL,
    release_period TEXT,
    access_method TEXT NOT NULL,
    local_path TEXT NOT NULL,
    source_url TEXT,
    evidence_class TEXT NOT NULL CHECK (evidence_class IN ('observed', 'reference', 'assumption')),
    limitations TEXT NOT NULL
);

CREATE TABLE sites (
    site_id TEXT PRIMARY KEY,
    site_name TEXT NOT NULL UNIQUE,
    study_area TEXT NOT NULL,
    state_code TEXT NOT NULL,
    benchmark_geography TEXT NOT NULL,
    allocation_share REAL NOT NULL CHECK (allocation_share >= 0 AND allocation_share <= 1),
    allocation_basis TEXT NOT NULL
);

CREATE TABLE roles (
    role_id TEXT PRIMARY KEY,
    planning_role TEXT NOT NULL UNIQUE,
    onet_soc_code TEXT NOT NULL,
    oews_soc_code TEXT NOT NULL,
    capacity_unit TEXT,
    direct_capacity_role INTEGER NOT NULL CHECK (direct_capacity_role IN (0, 1))
);

CREATE TABLE workload_daily_source (
    source_date TEXT PRIMARY KEY,
    source_sheet TEXT NOT NULL,
    source_lines INTEGER NOT NULL CHECK (source_lines >= 0),
    distinct_invoice_ids INTEGER NOT NULL CHECK (distinct_invoice_ids >= 0),
    positive_quantity_lines INTEGER NOT NULL CHECK (positive_quantity_lines >= 0),
    positive_units INTEGER NOT NULL CHECK (positive_units >= 0),
    nonpositive_quantity_lines INTEGER NOT NULL CHECK (nonpositive_quantity_lines >= 0),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id)
);

CREATE TABLE wage_benchmarks (
    release_period TEXT NOT NULL,
    benchmark_area TEXT NOT NULL,
    role_id TEXT NOT NULL REFERENCES roles(role_id),
    occupation_title TEXT NOT NULL,
    employment INTEGER NOT NULL CHECK (employment >= 0),
    mean_hourly_wage REAL NOT NULL CHECK (mean_hourly_wage > 0),
    median_hourly_wage REAL NOT NULL CHECK (median_hourly_wage > 0),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    PRIMARY KEY (release_period, benchmark_area, role_id)
);

CREATE TABLE regional_industry_benchmarks (
    benchmark_year INTEGER NOT NULL,
    geography_name TEXT NOT NULL,
    state_fips TEXT NOT NULL,
    county_fips TEXT NOT NULL,
    naics_code TEXT NOT NULL,
    establishments INTEGER NOT NULL CHECK (establishments >= 0),
    employment INTEGER NOT NULL CHECK (employment >= 0),
    annual_payroll_thousands INTEGER NOT NULL CHECK (annual_payroll_thousands >= 0),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    PRIMARY KEY (benchmark_year, state_fips, county_fips, naics_code)
);

CREATE TABLE qcew_industry_benchmarks (
    benchmark_year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    area_fips TEXT NOT NULL,
    geography_name TEXT NOT NULL,
    naics_code TEXT NOT NULL,
    ownership_code TEXT NOT NULL,
    establishments INTEGER NOT NULL CHECK (establishments >= 0),
    month3_employment INTEGER NOT NULL CHECK (month3_employment >= 0),
    average_weekly_wage INTEGER NOT NULL CHECK (average_weekly_wage >= 0),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    PRIMARY KEY (benchmark_year, quarter, area_fips, naics_code, ownership_code)
);

CREATE TABLE qwi_labor_flows (
    state_fips TEXT NOT NULL,
    county_fips TEXT NOT NULL,
    geography_name TEXT NOT NULL,
    quarter TEXT NOT NULL,
    naics_code TEXT NOT NULL,
    beginning_employment INTEGER,
    end_employment INTEGER,
    separations INTEGER,
    hires INTEGER,
    stable_employment INTEGER,
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    PRIMARY KEY (state_fips, county_fips, quarter, naics_code)
);

CREATE TABLE scenario_assumptions (
    assumption_key TEXT PRIMARY KEY,
    numeric_value REAL,
    text_value TEXT,
    unit TEXT NOT NULL,
    classification TEXT NOT NULL CHECK (classification IN ('observed_source_derived', 'design_decision', 'assumed', 'source_informed_uncalibrated')),
    basis TEXT NOT NULL,
    CHECK ((numeric_value IS NOT NULL) <> (text_value IS NOT NULL))
);

CREATE TABLE data_quality_results (
    check_name TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    observed_value TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    detail TEXT NOT NULL
);

CREATE TABLE planning_runs (
    run_id TEXT PRIMARY KEY,
    scenario_name TEXT NOT NULL,
    productivity_case TEXT NOT NULL CHECK (productivity_case IN ('low', 'base', 'high')),
    source_window_start TEXT NOT NULL,
    source_window_end TEXT NOT NULL,
    demand_scale REAL NOT NULL CHECK (demand_scale > 0),
    service_target REAL NOT NULL CHECK (service_target > 0 AND service_target <= 1),
    staffing_basis TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE staffing_plans (
    run_id TEXT NOT NULL REFERENCES planning_runs(run_id) ON DELETE CASCADE,
    site_id TEXT NOT NULL REFERENCES sites(site_id),
    role_id TEXT NOT NULL REFERENCES roles(role_id),
    scheduled_headcount INTEGER NOT NULL CHECK (scheduled_headcount >= 0),
    paid_hours_per_person REAL NOT NULL CHECK (paid_hours_per_person >= 0),
    median_hourly_wage REAL NOT NULL CHECK (median_hourly_wage > 0),
    staffing_rule TEXT NOT NULL,
    PRIMARY KEY (run_id, site_id, role_id)
);

CREATE TABLE modeled_daily_workload (
    run_id TEXT NOT NULL REFERENCES planning_runs(run_id) ON DELETE CASCADE,
    planning_date TEXT NOT NULL,
    source_date TEXT REFERENCES workload_daily_source(source_date),
    source_record_present INTEGER NOT NULL CHECK (source_record_present IN (0, 1)),
    site_id TEXT NOT NULL REFERENCES sites(site_id),
    modeled_orders INTEGER NOT NULL CHECK (modeled_orders >= 0),
    modeled_order_lines INTEGER NOT NULL CHECK (modeled_order_lines >= 0),
    modeled_units INTEGER NOT NULL CHECK (modeled_units >= 0),
    modeled_pack_jobs INTEGER NOT NULL CHECK (modeled_pack_jobs >= 0),
    PRIMARY KEY (run_id, planning_date, site_id)
);

CREATE TABLE daily_capacity_results (
    run_id TEXT NOT NULL REFERENCES planning_runs(run_id) ON DELETE CASCADE,
    planning_date TEXT NOT NULL,
    site_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    workload_quantity INTEGER NOT NULL CHECK (workload_quantity >= 0),
    productivity_rate REAL NOT NULL CHECK (productivity_rate > 0),
    required_hours REAL NOT NULL CHECK (required_hours >= 0),
    scheduled_headcount INTEGER NOT NULL CHECK (scheduled_headcount >= 0),
    available_productive_hours REAL NOT NULL CHECK (available_productive_hours >= 0),
    capacity_quantity REAL NOT NULL CHECK (capacity_quantity >= 0),
    completed_quantity REAL NOT NULL CHECK (completed_quantity >= 0),
    capacity_gap_hours REAL NOT NULL CHECK (capacity_gap_hours >= 0),
    surplus_hours REAL NOT NULL CHECK (surplus_hours >= 0),
    coverage_rate REAL NOT NULL CHECK (coverage_rate >= 0 AND coverage_rate <= 1),
    service_target_met INTEGER NOT NULL CHECK (service_target_met IN (0, 1)),
    scheduled_wage_cost REAL NOT NULL CHECK (scheduled_wage_cost >= 0),
    PRIMARY KEY (run_id, planning_date, site_id, role_id),
    FOREIGN KEY (run_id, planning_date, site_id) REFERENCES modeled_daily_workload(run_id, planning_date, site_id),
    FOREIGN KEY (run_id, site_id, role_id) REFERENCES staffing_plans(run_id, site_id, role_id)
);

CREATE TABLE planning_quality_results (
    check_name TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    observed_value TEXT NOT NULL,
    expected_value TEXT NOT NULL
);

CREATE VIEW planning_run_summary AS
WITH
day_counts AS (
    SELECT run_id, COUNT(DISTINCT planning_date) AS calendar_days
    FROM modeled_daily_workload
    GROUP BY run_id
),
workload_totals AS (
    SELECT run_id,
           SUM(modeled_orders) AS modeled_orders,
           SUM(modeled_order_lines) AS modeled_order_lines,
           SUM(modeled_units) AS modeled_units
    FROM modeled_daily_workload
    GROUP BY run_id
),
capacity_totals AS (
    SELECT run_id,
           SUM(capacity_gap_hours) AS total_gap_hours,
           AVG(service_target_met) AS role_site_day_service_rate,
           SUM(scheduled_wage_cost) AS direct_scheduled_wage_cost
    FROM daily_capacity_results
    GROUP BY run_id
),
staffing_totals AS (
    SELECT s.run_id,
           SUM(s.scheduled_headcount) AS daily_active_positions,
           SUM(s.scheduled_headcount * s.paid_hours_per_person * s.median_hourly_wage) AS daily_all_role_wage_cost
    FROM staffing_plans s
    GROUP BY s.run_id
)
SELECT r.run_id,
       r.productivity_case,
       d.calendar_days,
       w.modeled_orders,
       w.modeled_order_lines,
       w.modeled_units,
       s.daily_active_positions,
       c.total_gap_hours,
       c.role_site_day_service_rate,
       c.direct_scheduled_wage_cost,
       s.daily_all_role_wage_cost * d.calendar_days AS all_role_scheduled_wage_cost
FROM planning_runs r
JOIN day_counts d USING (run_id)
JOIN workload_totals w USING (run_id)
JOIN capacity_totals c USING (run_id)
JOIN staffing_totals s USING (run_id);

CREATE INDEX idx_workload_source_id ON workload_daily_source(source_id);
CREATE INDEX idx_wages_role ON wage_benchmarks(role_id);
CREATE INDEX idx_regional_naics ON regional_industry_benchmarks(naics_code);
CREATE INDEX idx_qcew_naics ON qcew_industry_benchmarks(naics_code);
CREATE INDEX idx_qwi_geography_period ON qwi_labor_flows(state_fips, county_fips, quarter);
CREATE INDEX idx_capacity_run_date ON daily_capacity_results(run_id, planning_date);
