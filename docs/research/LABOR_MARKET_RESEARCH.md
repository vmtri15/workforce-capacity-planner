# Labor Market Research

## Purpose

This file documents the public labor-market evidence used to choose the three
study areas and the sources that may be used in the capacity planner. It is
context for planning assumptions. 

## County Business Patterns: warehousing and storage

Source: U.S. Census Bureau, 2023 County Business Patterns API, NAICS 493
(`Warehousing and storage`). Employment is the number of employees during the
week of March 12; annual payroll is reported in thousands of dollars.

| Study area | County benchmark | Establishments | Employment | Annual payroll |
| --- | --- | ---: | ---: | ---: |
| Joliet/Elwood | Will County, IL | 203 | 27,224 | $1.365B |
| O'Hare logistics cluster | Cook County, IL | 262 | 18,849 | $1.149B |
| O'Hare logistics cluster | DuPage County, IL | 112 | 4,728 | $266.5M |
| Kenosha/Pleasant Prairie | Kenosha County, WI | 24 | 5,743 | $300.5M |

The figures confirm that each study area has a measurable warehousing and
storage employer base. They do **not** measure e-commerce-only facilities,
order volume, shift structure, productivity, vacancies, or an individual
facility's headcount.

Raw API responses are saved under `data/raw/census/`. The Census API key stays
only in `.env` and is never committed.

## Wage benchmark geography

The planner will use OEWS area benchmarks for labor-cost scenarios, not claim
them as a facility's actual pay rate.

| Study area | OEWS benchmark area | Why this is the correct public comparison |
| --- | --- | --- |
| Joliet/Elwood | Chicago-Naperville-Elgin, IL-IN | Will County is included in this OEWS area. |
| O'Hare logistics cluster | Chicago-Naperville-Elgin, IL-IN | Cook and DuPage Counties are included in this OEWS area. |
| Kenosha/Pleasant Prairie | Kenosha, WI | Kenosha County is published as its own OEWS area. |

The first two areas therefore use one shared regional wage benchmark. Kenosha
gets a separate local benchmark, which makes a comparison possible without
pretending the labor markets are identical.

## Roles and wage codes to retrieve

| Planning role | O*NET mapping | OEWS occupation to price |
| --- | --- | --- |
| Fulfillment associate | 53-7065 Stockers and Order Fillers | 53-7065 Stockers and Order Fillers |
| Packing associate | 53-7064 Packers and Packagers, Hand | 53-7064 Packers and Packagers, Hand |
| Shipping and receiving coordinator | 43-5071 Shipping, Receiving, and Inventory Clerks | 43-5071 Shipping, Receiving, and Inventory Clerks |
| Warehouse supervisor | 53-1042 First-Line Supervisors of Helpers, Laborers, and Material Movers, Hand | Match the current OEWS title/code carefully because SOC revisions can rename or recode this supervisory occupation. |

May 2025 OEWS role extracts are saved in `data/raw/bls/oews_2025/` and the
model-ready compact table is `data/processed/oews_2025_role_wage_benchmarks.csv`.
Use published median and mean hourly wages as scenario inputs. Wage data does
not set staffing need; workload, usable labor hours, and a separately
documented productivity assumption do that.

## Evidence limits and next modeling decision

The data now supports a defensible regional context, role taxonomy, and a
future labor-cost module. The missing piece is still a calibrated
`units per productive hour` input for picking and packing. The historical order
and warehouse datasets can shape volume and mix scenarios, but neither alone
proves a worker-level rate. The first working model should expose that rate as
a low/base/high assumption and label it as uncalibrated until a source with
labor-time fields is found.

## Official source links

- Census County Business Patterns API: https://www.census.gov/data/developers/data-sets/cbp-zbp/cbp-api.html
- BLS May 2025 OEWS area definitions: https://www.bls.gov/oes/2025/may/msa_def.htm
- BLS OEWS tables: https://www.bls.gov/oes/tables.htm
- BLS May 2023 Chicago OEWS table, retained as a historical benchmark while the
  May 2025 bulk download is being obtained: https://www.bls.gov/oes/2023/May/oes_16980.htm
