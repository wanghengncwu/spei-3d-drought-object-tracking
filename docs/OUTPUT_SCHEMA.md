# Output schema

All tabular outputs are UTF-8 CSV files. Areas are expressed in square kilometres and area–duration quantities in square-kilometre months.

## `events_table.csv` and `raw_events_table.csv`

| Column | Definition |
|---|---|
| `event_id` | Deterministic canonical object identifier within the run |
| `start_time` | First active calendar month |
| `end_time` | Last active calendar month |
| `duration_months` | Inclusive calendar duration from start to end |
| `active_months` | Number of months containing the object |
| `AD_km2months` | Sum of monthly object areas |
| `cumulative_catalogue_severity` | Unweighted sum of negative SPEI over all object grid-cell months |
| `threshold_deficit_severity_km2months` | Area-weighted accumulation of the deficit below the configured threshold |
| `mean_intensity_deficit` | Threshold-deficit severity divided by AD |
| `peak_intensity_deficit` | Maximum threshold deficit within the object |
| `gridcell_months` | Total number of active grid-cell months |
| `max_inst_area_km2` | Largest single connected patch area attained by the object |
| `max_monthly_object_area_km2` | Largest total monthly area assigned to the object |

`raw_events_table.csv` is written before duration and peak-area filtering. `events_table.csv` contains the retained catalogue.

## `event_monthly_stats.csv`

| Column | Definition |
|---|---|
| `event_id` | Retained object identifier |
| `time_index` | Zero-based monthly index in the selected input |
| `time` | Calendar date associated with the monthly field |
| `area_km2` | Total object area in the month |
| `catalogue_severity` | Monthly unweighted negative-SPEI accumulation |
| `threshold_deficit_severity_km2months` | Monthly area-weighted threshold-deficit severity |
| `gridcell_count` | Number of active grid cells |
| `maximum_patch_area_km2` | Largest connected patch assigned to the object in that month |
| `minimum_spei` | Lowest SPEI within the monthly object footprint |

## `annual_active_year_summary.csv`

| Column | Definition |
|---|---|
| `year` | Calendar year |
| `active_object_count` | Number of retained objects active during the year |
| `AD_km2months` | Sum of monthly AD contributions occurring during the year |
| `cumulative_catalogue_severity` | Sum of monthly catalogue severity occurring during the year |
| `threshold_deficit_severity_km2months` | Sum of monthly threshold-deficit severity occurring during the year |
| `onset_object_count` | Number of retained objects beginning during the year |

## `link_diagnostics_monthly.csv`

| Column | Definition |
|---|---|
| `time_index` | Zero-based monthly index |
| `time` | Calendar date |
| `patch_count` | Number of retained monthly patches |
| `new_patch_count` | Patches initiating new objects |
| `linked_patch_count` | Patches inheriting an existing object ID |
| `merge_patch_count` | Current patches overlapping more than one eligible parent |
| `split_parent_count` | Parent objects linked to more than one current patch |
| `union_operations` | Parent-lineage unions under the overlap-union rule |

## `sensitivity_summary.csv`

Each row represents one unique one-factor-at-a-time scenario and records the varied factor, level, full extraction settings, raw and retained object counts, total AD, total catalogue severity, and AD-ranked upper-decile contribution shares.

## `run_manifest.json`

The manifest records:

- software, algorithm, Python, and dependency versions;
- input file names and sizes, without local absolute paths;
- optional SHA-256 input fingerprints;
- selected time coverage and grid dimensions/ranges;
- event-definition and linking parameters;
- raw and retained object counts;
- merge, split, and union diagnostics;
- catalogue totals and upper-decile shares;
- runtime in seconds.
