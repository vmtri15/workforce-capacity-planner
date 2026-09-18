# JTH recruiting validation

## Decision

Use JTH to demonstrate a generic recruiting-funnel workflow, with visible missing
stages and privacy-altered dates. Do not use it to calibrate warehouse hiring
lead times, employee start dates, onboarding or productive readiness.

## Verified findings

- 6,011 jobs and 42,288 application histories were inspected.
- 4,722 jobs have no manually entered job category. Populated categories are
  predominantly technical roles.
- A warehouse/logistics keyword screen finds no matches in manual category/
  expertise fields or LLM-derived role-category fields. It finds 34 jobs and
  260 linked histories through LLM-derived industry labels. Industry is not role;
  these are not confirmed warehouse-worker applications. Missing categories and
  keyword limitations prevent concluding that no warehouse jobs exist.
- All populated date fields parse. No reversed observed stage sequences or
  end dates earlier than the latest observed stage were found. Source documentation
  states that dates were privacy-shifted and monotonically sorted; ordering alone
  does not prove accurate elapsed times.
- Only 51 records have both spontaneous-application and acceptance dates.
  Their durations cannot represent the full recruitment population.
- 696 have shortlist and acceptance dates. One interval spans 1,136 days and
  requires source-context review before interpretation.
- 856 have offer and acceptance dates; 492 are same-day. Five-day-scale date
  perturbation means these are not precise measurements of offer decision speed.
- 31,240 lack an end-of-process date. Do not label these rejected, completed,
  or currently active without additional evidence and an observation cutoff.

## Portfolio implementation boundary

A future recruiting view may display observed stage counts, missing-date coverage,
and endpoint-paired exploratory intervals with their denominators. Counts of
non-null stage dates are not unconditional conversion rates because paths can
skip stages or have missing records. Offer acceptance must remain separate from
worker start and training completion. Warehouse hiring-delay assumptions stay
configurable and explicitly synthetic.

Reproduce with `python scripts/validate_jth_recruiting.py`. The aggregate output
is `data/processed/jth_recruiting_validation.json`; it records source hashes,
screen terms, stage coverage and interval summaries. No optimizer inputs changed.

Source: https://zenodo.org/records/21390581, CC BY-NC 4.0. The current downloaded
dataset card specifies a five-day Laplace noise scale for dates.
