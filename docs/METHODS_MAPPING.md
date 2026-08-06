# Mapping between manuscript methods and repository code

This document maps the documented drought-object workflow to the corresponding implementation modules.

| Manuscript component | Implementation | Main files |
|---|---|---|
| Precomputed SPEI input | Reads SPEI fields and coordinate metadata from NetCDF | `src/spei3d/io.py` |
| Monthly drought definition | Applies the configured SPEI threshold | `src/spei3d/engine.py` |
| Monthly 2-D connectivity | Labels 4- or 8-neighbour drought patches | `src/spei3d/patches.py` |
| Monthly patch-area filtering | Removes patches below the configured true-area threshold | `src/spei3d/patches.py`, `src/spei3d/geo.py` |
| Adjacent-month temporal linking | Implements maximum overlap, overlap union, and maximum IoU | `src/spei3d/linking.py` |
| Merge and split treatment | Applies deterministic event-ID inheritance and transition diagnostics | `src/spei3d/linking.py` |
| Duration and peak-area filtering | Retains objects satisfying persistence and peak-area criteria | `src/spei3d/catalogue.py` |
| AD and catalogue severity | Aggregates monthly object area and unweighted negative SPEI | `src/spei3d/catalogue.py` |
| Threshold-deficit severity and intensity | Calculates area-weighted deficit severity and intensity diagnostics | `src/spei3d/patches.py`, `src/spei3d/catalogue.py` |
| Active-year summaries | Allocates monthly object contributions to calendar years | `src/spei3d/catalogue.py`, `src/spei3d/engine.py` |
| Object-definition sensitivity | Varies one object-selection threshold at a time | `src/spei3d/sensitivity.py` |
| Accumulation-scale sensitivity | Uses independently supplied SPEI-03, SPEI-06, and SPEI-12 inputs | `src/spei3d/sensitivity.py` |
| Drought-threshold sensitivity | Re-runs extraction for independently configured SPEI thresholds | `src/spei3d/sensitivity.py` |
| Linking-rule sensitivity | Re-runs extraction under the three documented linking rules | `src/spei3d/sensitivity.py` |
| Run metadata and completion checks | Writes configuration, software, dependency, input, grid, and result summaries | `src/spei3d/engine.py`, `src/spei3d/io.py` |
| Command-line interface | Validates configurations and runs extraction or sensitivity workflows | `src/spei3d/cli.py` |
