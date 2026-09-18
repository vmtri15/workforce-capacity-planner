# Operational research downloads and initial audit

## Sources and reproduction

- OpenPack release: https://zenodo.org/records/8145223 (CC BY-NC-SA 4.0).
- JTH release: https://zenodo.org/records/21390581 (CC BY-NC 4.0).
- Download with `python scripts/fetch_operational_research.py`, then profile with
  `python scripts/profile_operational_research.py`.
- This run used `/opt/anaconda3/bin/python3`; the other local Python runtime
  failed HTTPS certificate verification. TLS verification was not disabled.

OpenPack annotations, incident labels and order sheets were selectively read
from all 21 recording archives using HTTP byte ranges. The 313 extracted CSVs
match the relevant release file index and pass ZIP member CRC checks. Raw files
and a SHA-256 manifest are in `data/raw/openpack_timing/` (about 6.2 MB of CSVs).
No full sensor/video downloads were needed. ZIP archive checksums were not
verified because only selected members were downloaded.

JTH `history.csv`, `jobs.csv`, `candidates.csv`, and `dataset_card.md` were fetched
from the record's file API and verified against published MD5 checksums. They are
stored in `data/raw/jth_data/`. No API key or account was required.

## OpenPack findings

- 104 annotated sessions, 2,029 box groups, 21 recording IDs representing 16
  people according to the subject documentation. Repeated IDs for the same
  person must be grouped in any train/test split.
- All annotated box groups join to session order sheets. No nonpositive operation
  durations or overlapping adjacent intervals within box groups were found.
- 2,013 of the 2,029 box groups have 1-5 items. Extrapolation to large wholesale
  orders or 12/24/48-unit jobs is not supported by this sample distribution.
- Core box handling is provisionally defined as Assemble Box, Insert Items,
  Close Box, Attach Box Label and Attach Shipping Label. Picking, item relabeling,
  scanning, paperwork and final placement are separate operations. This core
  definition is NOT the full productive labor demand of a packing station.
- One box, U0202/S0500/15, has no core-handling duration and is flagged for review.
  Incident labels are retained, but not yet used to exclude affected observations.
- Summaries are descriptive, include incomplete/problem records, and are split
  by experimental scenario. S3 includes preassembled boxes/irregular operations;
  S4 adds time pressure. They must not be pooled into a single staffing standard.

`data/processed/openpack_box_timing.csv` preserves per-box timing and item count.
`data/processed/operational_research_profile.json` contains descriptive summaries.
No replacement planner productivity rate has been adopted.

## JTH findings

- 42,288 application histories, 6,011 jobs and 37,554 candidates. Candidate and
  job IDs are unique; all history references resolve to those tables.
- Only 3,417 histories contain a spontaneous-application date. Missing earlier
  stages cannot be treated as zero-length steps or evidence of rejection.
- 857 records have offer acceptance dates, but only 856 also have offer dates.
  Accepted does not establish an employee start date or training readiness.
- The current downloaded card specifies a five-day Laplace noise scale for dates
  with monotonic sorting. An older bundled card states a different amount;
  use the downloaded release card. Same-day stages are not exact measured times.
- These are French recruiting records, not a verified warehouse-role hiring
  population. Suitable first uses are funnel structure and exploratory scenario
  analysis, not direct calibration of our warehouse hiring delays.

## Next validation gate

### Packing annotation audit completed

Run `python scripts/validate_openpack_timing.py` after the profile script.
The audit verifies downloaded CSV hashes and joins temporal incident/recovery
annotations to individual operation intervals. Additional work, parallel work,
investigation and struggling annotations are retained rather than classified as
incidents automatically. Distinct-person IDs reconcile the five repeated people.

Of 2,029 box groups, 325 overlap incident/recovery annotations, seven lack at
least one core operation label, and 62 contain Null/System Error labels (counts
overlap). 186 contain elapsed gaps between annotated operations. No negative
aggregate gap was found. These records remain in the audit, not deleted.

1,650 pass the provisional screen for core labels, incident/recovery overlap,
and Null/System Error labels. This is not a certification of complete cycles:
elapsed gaps are separately flagged, and preassembled boxes can legitimately
lack assembly. Station work includes box handling, item relabeling, scanning,
paperwork and final placement. Picking is reported separately. Incident durations
are not added again to operation durations, avoiding overlapping-time inflation.

Outputs: `data/processed/openpack_timing_audit.csv` and
`data/processed/openpack_timing_validation.json`. Scenario-specific descriptive
summaries remain experimental references. No optimizer rates were changed.

Review OpenPack boundary/incident cases and map the complete packing-station
workflow before fitting time estimates. Segment by scenario and item count and
hold out distinct people. Inspect JTH role coverage and missing-stage patterns
before estimating any delay distributions. Keep these studies separate from
the footwear workload and synthetic attendance datasets; there is no shared
worker or facility key across sources.
