import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from spei3d.config import load_config
from spei3d.engine import run_extraction


def write_synthetic_spei(path: Path) -> None:
    values = np.zeros((4, 5, 7), dtype=np.float32)
    values[0, 2, 0:2] = -2.0
    values[0, 2, 4:6] = -2.0
    values[1, 2, 0:6] = -2.0
    values[2, 2, 0:2] = -2.0
    values[2, 2, 4:6] = -2.0
    values[2, 4, 6] = -2.0
    values[3, 2, 0:2] = -2.0
    values[3, 4, 6] = -2.0
    dataset = xr.Dataset(
        {"spei": (("time", "lat", "lon"), values)},
        coords={
            "time": pd.date_range("2000-01-01", periods=4, freq="MS"),
            "lat": np.arange(5, dtype=float),
            "lon": np.arange(7, dtype=float),
        },
    )
    dataset.to_netcdf(path, engine="scipy")


def test_run_extraction_writes_retained_catalogue_and_diagnostics(tmp_path: Path) -> None:
    spei = tmp_path / "spei.nc"
    write_synthetic_spei(spei)
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        f"""
input:
  spei: {spei.name}
  dataset_name: synthetic
  variable: spei
output:
  root: output
event_definition:
  spei_threshold: -1.0
  connectivity: 8
  minimum_monthly_patch_area_km2: 0
  minimum_duration_months: 2
  minimum_peak_area_km2: 0
linking:
  rule: maximum_overlap
  minimum_overlap_cells: 1
  minimum_iou: 0.10
runtime:
  time_block_months: 2
  write_labels: false
  overwrite: false
  hash_inputs: true
""",
        encoding="utf-8",
    )
    summary = run_extraction(load_config(config_path))
    assert summary.object_count == 2
    events = pd.read_csv(tmp_path / "output" / "events_table.csv")
    assert sorted(events["duration_months"].tolist()) == [2, 4]
    diagnostics = pd.read_csv(tmp_path / "output" / "link_diagnostics_monthly.csv")
    assert diagnostics["merge_patch_count"].sum() == 1
    assert diagnostics["split_parent_count"].sum() == 1
    assert (tmp_path / "output" / "event_monthly_stats.csv").exists()
    assert (tmp_path / "output" / "annual_active_year_summary.csv").exists()
    manifest_path = tmp_path / "output" / "run_manifest.json"
    assert manifest_path.exists()
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in manifest_text
    manifest = json.loads(manifest_text)
    assert manifest["software"] == {
        "name": "spei-3d-drought-object-tracking",
        "title": "SPEI-Based 3-D Drought Object Tracking",
        "version": "1.0.0",
        "algorithm_version": "1.0",
    }
    assert manifest["input"]["spei"]["sha256"]
    assert len(manifest["input"]["spei"]["sha256"]) == 64
    assert manifest["coverage"] == {
        "start_time": "2000-01-01",
        "end_time": "2000-04-01",
    }
    assert manifest["grid"]["latitude_min"] == 0.0
    assert manifest["grid"]["latitude_max"] == 4.0
    assert manifest["dependencies"]["numpy"]
