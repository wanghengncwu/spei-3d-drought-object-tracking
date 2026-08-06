from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from spei3d.config import load_config
from spei3d.sensitivity import build_scenarios, run_sensitivity


def write_spei(path: Path) -> None:
    values = np.zeros((2, 2, 3), dtype=np.float32)
    values[:, 0, 0:2] = -2.0
    xr.Dataset(
        {"spei": (("time", "lat", "lon"), values)},
        coords={
            "time": pd.date_range("2000-01-01", periods=2, freq="MS"),
            "lat": [0.0, 1.0],
            "lon": [0.0, 1.0, 2.0],
        },
    ).to_netcdf(path, engine="scipy")


def test_build_scenarios_is_one_factor_at_a_time_and_deduplicated(tmp_path: Path) -> None:
    for scale in (3, 6, 12):
        (tmp_path / f"spei{scale:02d}.nc").touch()
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
input:
  spei: spei06.nc
  dataset_name: test
output:
  root: outputs
event_definition:
  spei_threshold: -1
  minimum_monthly_patch_area_km2: 25000
  minimum_duration_months: 3
  minimum_peak_area_km2: 50000
linking:
  rule: maximum_overlap
  minimum_iou: 0.10
sensitivity:
  baseline_scale_months: 6
  accumulation_scales: [3, 6, 12]
  scale_inputs: {3: spei03.nc, 6: spei06.nc, 12: spei12.nc}
  spei_thresholds: [-1, -1.5, -2]
  monthly_patch_areas_km2: [10000, 25000, 50000]
  minimum_durations_months: [1, 3, 6]
  minimum_peak_areas_km2: [25000, 50000, 100000]
  linking_rules:
    - {rule: maximum_overlap, minimum_iou: 0.0}
    - {rule: overlap_union, minimum_iou: 0.0}
    - {rule: maximum_iou, minimum_iou: 0.10}
""",
        encoding="utf-8",
    )
    scenarios = build_scenarios(load_config(config_path))
    assert len(scenarios) == 13
    assert len({scenario.name for scenario in scenarios}) == 13
    assert len({scenario.signature for scenario in scenarios}) == 13
    for scenario in scenarios[1:]:
        assert scenario.factor in {
            "accumulation_scale",
            "spei_threshold",
            "monthly_patch_area",
            "minimum_duration",
            "minimum_peak_area",
            "linking_rule",
        }


def test_run_sensitivity_writes_summary(tmp_path: Path) -> None:
    spei = tmp_path / "spei06.nc"
    write_spei(spei)
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
input:
  spei: spei06.nc
  dataset_name: test
output:
  root: sensitivity_output
event_definition:
  minimum_monthly_patch_area_km2: 0
  minimum_duration_months: 1
  minimum_peak_area_km2: 0
runtime:
  overwrite: true
sensitivity:
  baseline_scale_months: 6
  spei_thresholds: [-1, -2]
""",
        encoding="utf-8",
    )
    summary_path = run_sensitivity(load_config(config_path))
    summary = pd.read_csv(summary_path)
    assert summary["scenario"].tolist() == ["baseline", "spei_threshold_m2p00"]
    assert set(summary["spei_file"]) == {"spei06.nc"}
    required = {
        "object_count",
        "total_AD_km2months",
        "total_catalogue_severity",
        "upper_decile_AD_share",
        "upper_decile_catalogue_severity_share",
    }
    assert required.issubset(summary.columns)
