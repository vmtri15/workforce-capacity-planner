# Role Wage Benchmarks

## Source and use

Source: BLS Occupational Employment and Wage Statistics (OEWS), May 2025,
cross-industry area estimates. The raw official responses are saved in
`data/raw/bls/oews_2025/`; the compact extracted table is
`data/processed/oews_2025_role_wage_benchmarks.csv`.

Use these as scenario inputs for direct wage cost. They are area-wide survey
estimates for wage-and-salary workers, not facility offer rates, total employer
labor cost, contractor rates, or evidence of productivity.

## Benchmarks

| Planning role | SOC used for wage benchmark | Chicago median hourly wage | Kenosha median hourly wage |
| --- | --- | ---: | ---: |
| Fulfillment associate | 53-7065 Stockers and Order Fillers | $18.48 | $22.13 |
| Packing associate | 53-7064 Packers and Packagers, Hand | $17.40 | $18.18 |
| Shipping and receiving coordinator | 43-5071 Shipping, Receiving, and Inventory Clerks | $22.95 | $23.02 |
| Warehouse supervisor | 53-1047 First-Line Supervisors of Transportation and Material Moving Workers, Except Aircraft Cargo Handling | $32.85 | $34.86 |

Chicago–Naperville–Elgin is the shared benchmark for the Joliet/Elwood and
O'Hare study areas. Kenosha, WI is the benchmark for Kenosha/Pleasant Prairie.

## SOC mapping note

The O*NET role research uses 53-1042 for the warehouse-supervisor planning
role. In the May 2025 OEWS area table, the comparable published supervisory
occupation is 53-1047. The model must preserve both codes and state that the
OEWS code is used only for the wage benchmark.

## Cost model treatment

The first model should expose a wage basis selector:

- `median hourly wage`: default wage-cost scenario input.
- `mean hourly wage`: alternative sensitivity input.
- `loaded labor multiplier`: an explicit assumption for benefits, payroll taxes,
  differentials, and other employer cost that OEWS does not include.

Do not convert annual wage into a shift wage with an assumed 2,080 hours when
the hourly OEWS estimate is available.

## Official links

- BLS May 2025 OEWS tables: https://www.bls.gov/oes/tables.htm
- BLS May 2025 area definitions: https://www.bls.gov/oes/2025/may/msa_def.htm
