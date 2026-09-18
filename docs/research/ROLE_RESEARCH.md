# Fulfillment Role Research

## Status

This is a research-backed starting model for the selected fulfillment/distribution facility type. It does not set workforce headcount, productivity rates, shift coverage ratios, or hiring requirements.

## Recommended role model

| Product role | O*NET occupation | Why it belongs in the model |
|---|---|---|
| Fulfillment associate | 53-7065.00 Stockers and Order Fillers | Covers inventory storage and retrieval for customer orders. Use this as the initial picking and replenishment capacity pool. |
| Packing associate | 53-7064.00 Packers and Packagers, Hand | Covers inspecting, counting, labeling, sealing, and moving completed packages. Keep packing capacity distinct from picking capacity. |
| Shipping and receiving coordinator | 43-5071.00 Shipping, Receiving, and Inventory Clerks | Covers shipment verification, records, shipping documents, discrepancies, and routing materials. This is an operational coordination role. |
| Warehouse supervisor | 53-1042.00 First-Line Supervisors of Helpers, Laborers, and Material Movers, Hand | Covers safety, task assignment, staffing requirements, training, and oversight of material-moving work. |

Forklift work may be represented as an additional skill/certification using 53-7051.00 Industrial Truck and Tractor Operators. Do not create a permanent dedicated forklift role unless the final workflow and workload data show it is necessary.

## Important distinction

The first two roles are direct production capacity. The coordinator and supervisor enable the process, but should not be assigned the same unit-per-hour formula as pickers or packers. Leadership coverage requirements must be sourced or introduced as editable assumptions later.

## Supporting O*NET evidence

- Stockers and Order Fillers includes order filler, order picker, stock clerk, stocker, warehouse technician, and warehouse worker as reported titles.
- Packers and Packagers, Hand includes packer, picker and packer, packaging specialist, and pack-out operator as reported titles. Core tasks include inspecting, counting, recording, sealing, labeling, and moving packages.
- Shipping, Receiving, and Inventory Clerks includes receiving associate, receiving coordinator, shipping coordinator, and order fulfillment specialist as reported titles. Core tasks include verifying shipments against records, preparing shipping documentation, recording discrepancies, and routing materials.
- First-Line Supervisors of Helpers, Laborers, and Material Movers, Hand includes warehouse supervisor, receiving supervisor, shipping supervisor, and floor supervisor as reported titles. Core tasks include maintaining safety, assigning duties, planning work schedules, estimating staffing requirements, and assessing training needs.

These statements were verified in the local O*NET Database 31.0 Excel release under `data/raw/db_31_0_excel/`. O*NET task evidence supports work definitions and skill mapping. It does not support a particular wage, headcount, productivity target, or training duration at our modeled sites.

## Pinned 2026 Tableau Extract

`scripts/export_onet_roles.py` now exports the four occupations, tasks, and
essential/transferable skill importance records to `tableau/onet_2026/` with
release labels, original record dates and source hashes. The local release's
Read Me confirms August 2026. No API key is needed to use this downloaded release.
Selected task and skill records are dated August 2026 for fulfillment, August
2020 for packing, August 2019 for shipping/receiving and August 2024 for supervisors.
The database release date does not make every underlying record a 2026 observation.
Numerical staffing, productivity and cost scenarios are unchanged.

## Next evidence needed

1. Obtain occupation-specific wage benchmarks for the study region.
2. Define the actual outbound workflow and map workload units to picking and packing work.
3. Identify defensible task-time or productivity distributions; do not convert industry averages into person-level output rates.
4. Decide whether inbound/receiving is in the MVP or treated as a later extension.

## Source

- Local O*NET Database 31.0 Excel release, downloaded 2026-09-13.
- [O*NET Online: Stockers and Order Fillers](https://www.onetonline.org/link/summary/53-7065.00)
- [O*NET Online: Packers and Packagers, Hand](https://www.onetonline.org/link/summary/53-7064.00)
- [O*NET Online: Shipping, Receiving, and Inventory Clerks](https://www.onetonline.org/link/summary/43-5071.00)
- [O*NET Online: First-Line Supervisors of Helpers, Laborers, and Material Movers, Hand](https://www.onetonline.org/link/summary/53-1042.00)

## September 15 literature review

See [Workforce learning and cross-training evidence](WORKFORCE_LEARNING_RESEARCH.md) for five full-text reviews, page references, applicability limits, and the packing research priority. Existing numerical model assumptions remain unchanged.
