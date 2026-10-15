# SPEI-Based 3-D Drought Object Tracking

A reproducible Python implementation for identifying and tracking three-dimensional meteorological drought objects in longitude–latitude–time space from precomputed Standardized Precipitation Evapotranspiration Index (SPEI) NetCDF files.

This repository accompanies the following article:

> Wang, H., Wang, F., Xu, C.-Y., Zhao, H., Huang, S., Yang, H., Zhang, H., Cui, L., and Du, Y. (2026). Spatiotemporal evolution and concentration of global meteorological drought from a three-dimensional object-based perspective. *Journal of Hydrology*, 680, 136473. https://doi.org/10.1016/j.jhydrol.2026.136473

## Capabilities

The software provides a reproducible workflow for:

- identifying monthly drought patches from precomputed SPEI fields;
- linking patches between immediately adjacent months;
- constructing and filtering 3-D drought objects;
- generating object-level, monthly, and annual catalogues;
- diagnosing merge and split transitions;
- evaluating sensitivity to SPEI accumulation scale, drought threshold, object-selection thresholds, and temporal-linking rule;
- recording software, input, parameter, grid, dependency, and result-summary metadata for reproducible runs.

## Software identifiers

| Item | Name |
|---|---|
| GitHub repository | `spei-3d-drought-object-tracking` |
| Python distribution | `spei-3d-drought-object-tracking` |
| Python import package | `spei3d` |
| Command-line program | `spei3d` |
| Release | `v1.0.0` |

## Workflow

For each monthly SPEI field, cells satisfying the configured drought threshold are grouped using two-dimensional 4- or 8-neighbour connectivity. Monthly patches below the configured area threshold are removed. Remaining patches are linked to patches in the immediately preceding calendar month. Missing calendar months are rejected rather than bridged.

Three temporal-linking rules are available:

1. `maximum_overlap`: the current patch inherits the event ID of the parent with the largest number of shared grid cells; ties retain the smaller existing event ID.
2. `overlap_union`: all overlapping parent lineages are merged into one canonical event.
3. `maximum_iou`: the parent with the largest intersection-over-union is retained when the configured IoU threshold is met.

Retained objects are filtered by minimum duration and minimum peak instantaneous area. The resulting catalogue reports area–duration (AD), cumulative catalogue severity, area-weighted threshold-deficit severity, mean and peak intensity, duration, active months, and maximum monthly area.

A direct mapping between manuscript methods and code modules is provided in [`docs/METHODS_MAPPING.md`](docs/METHODS_MAPPING.md).

## System requirements

- Python 3.10 or newer;
- Windows, macOS, or Linux;
- sufficient storage and memory for the selected NetCDF files and output catalogues.

All input and output paths are supplied through YAML configuration files.

## Installation

### Option A: standard Python environment

Create an environment:

```bash
python -m venv .venv
```

Activate it:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bat
:: Windows Command Prompt
.venv\Scripts\activate.bat
```

```bash
# macOS or Linux
source .venv/bin/activate
```

Install the package:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Install optional Zarr event-label support:

```bash
python -m pip install -e ".[labels]"
```

Install development and release-verification dependencies:

```bash
python -m pip install -e ".[dev,labels]"
```

### Option B: Conda or Miniforge

```bash
conda env create -f environment.yml
conda activate spei3d
```

## Input contract

The primary input is a NetCDF file containing one three-dimensional SPEI variable with dimensions equivalent to:

```text
time × latitude × longitude
```

The loader recognizes:

- `lat` or `latitude`;
- `lon` or `longitude`;
- `time` or `valid_time`.

The input must satisfy the following conditions:

- one value per consecutive calendar month;
- strictly ordered and unique time coordinates;
- one-dimensional, finite, unique, monotonic, and regularly spaced latitude and longitude coordinates;
- a SPEI variable containing the `time`, `lat`, and `lon` dimensions.

A land mask can be supplied as a Boolean-compatible NumPy array or as a two-dimensional NetCDF latitude–longitude variable. A target-grid NetCDF file can be supplied to interpolate an input field to the analysis grid before extraction.

## Baseline extraction

Copy the portable example configuration:

```powershell
# Windows PowerShell
Copy-Item configs\baseline.example.yml configs\baseline.yml
```

```bat
:: Windows Command Prompt
copy configs\baseline.example.yml configs\baseline.yml
```

```bash
# macOS or Linux
cp configs/baseline.example.yml configs/baseline.yml
```

Edit the input and output paths in `configs/baseline.yml`, then run:

```bash
spei3d validate-config --config configs/baseline.yml
spei3d extract --config configs/baseline.yml
```

The example baseline corresponds to the manuscript settings:

- SPEI threshold: `−1.0`;
- monthly spatial connectivity: 8-neighbour;
- minimum monthly patch area: `25,000 km²`;
- minimum duration: `3 months`;
- minimum peak instantaneous area: `50,000 km²`;
- temporal-linking rule: `maximum_overlap`.

## Sensitivity experiments

Copy and edit the sensitivity configuration:

```powershell
# Windows PowerShell
Copy-Item configs\sensitivity.example.yml configs\sensitivity.yml
```

```bat
:: Windows Command Prompt
copy configs\sensitivity.example.yml configs\sensitivity.yml
```

```bash
# macOS or Linux
cp configs/sensitivity.example.yml configs/sensitivity.yml
```

Run:

```bash
spei3d validate-config --config configs/sensitivity.yml
spei3d sensitivity --config configs/sensitivity.yml
```

The example configuration defines the one-factor-at-a-time experiments reported in the supplementary analysis:

- SPEI accumulation scales: 3, 6, and 12 months;
- SPEI thresholds: −1.0, −1.5, and −2.0;
- monthly patch areas: 10,000, 25,000, and 50,000 km²;
- minimum durations: 1, 3, and 6 months;
- minimum peak areas: 25,000, 50,000, and 100,000 km²;
- maximum-overlap, overlap-union, and maximum-IoU linking rules.

Identical parameter combinations are removed automatically.

## Outputs

Each extraction directory contains:

| File | Purpose |
|---|---|
| `events_table.csv` | Retained 3-D drought-object catalogue |
| `raw_events_table.csv` | Catalogue before duration and peak-area filtering |
| `event_monthly_stats.csv` | Retained object metrics for each active month |
| `annual_active_year_summary.csv` | Active-year object count, AD, and severity summaries |
| `link_diagnostics_monthly.csv` | Monthly new, linked, merge, split, and union diagnostics |
| `run_manifest.json` | Software, input, parameter, grid, dependency, and summary metadata |
| `events_3d.zarr` | Optional filtered event-label cube |
| `run.ok` | Successful-completion marker |

The sensitivity workflow additionally creates `sensitivity_summary.csv` and one output directory per unique scenario. Complete field definitions are provided in [`docs/OUTPUT_SCHEMA.md`](docs/OUTPUT_SCHEMA.md).

## Reproducibility safeguards

- Relative paths are resolved from the YAML file location.
- Existing non-empty output directories are protected unless `runtime.overwrite: true`.
- Missing calendar months are rejected; the code never links across a temporal gap.
- Equal-overlap ties are resolved deterministically using the smaller existing event ID.
- The AD-ranked upper decile uses `ceil(0.10 × N)` objects.
- `run_manifest.json` records software and dependency versions without recording local absolute paths.
- Optional SHA-256 input fingerprints can be enabled with `runtime.hash_inputs: true`.

See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) for the recommended archival workflow.

## Verification

Install development dependencies and run:

```bash
python scripts/verify_release.py
```

The verification workflow runs Ruff, executes the synthetic test suite, audits repository hygiene, and builds both wheel and source distributions in a temporary directory.

Individual checks can also be run with:

```bash
python -m pytest
python -m ruff check .
python scripts/audit_release.py .
```

## Citation

If you use this software, workflow, or its outputs, please cite the associated article:

> Wang, H., Wang, F., Xu, C.-Y., Zhao, H., Huang, S., Yang, H., Zhang, H., Cui, L., and Du, Y. (2026). Spatiotemporal evolution and concentration of global meteorological drought from a three-dimensional object-based perspective. *Journal of Hydrology*, 680, 136473. https://doi.org/10.1016/j.jhydrol.2026.136473

The repository-root `CITATION.cff` file provides machine-readable citation metadata for both the software release and the associated article. GitHub displays these metadata through the **Cite this repository** control.

## GitHub publication

A complete Windows-oriented upload and release guide is provided in [`docs/GITHUB_UPLOAD_GUIDE_CN.md`](docs/GITHUB_UPLOAD_GUIDE_CN.md).

Recommended repository description:

> Reproducible SPEI-based tracking and sensitivity analysis of 3-D meteorological drought objects.

Recommended topics:

`drought`, `spei`, `meteorological-drought`, `event-tracking`, `climate`, `python`, `reproducible-research`

## License

MIT License. See [`LICENSE`](LICENSE).
