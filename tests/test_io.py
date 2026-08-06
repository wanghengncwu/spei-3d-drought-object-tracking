from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from spei3d.config import InputConfig
from spei3d.io import open_spei


def write_spei(path: Path, times: pd.DatetimeIndex) -> None:
    values = np.zeros((len(times), 2, 3), dtype=np.float32)
    xr.Dataset(
        {"spei": (("time", "lat", "lon"), values)},
        coords={"time": times, "lat": [-0.5, 0.5], "lon": [0.0, 1.0, 2.0]},
    ).to_netcdf(path, engine="scipy")


def input_config(path: Path) -> InputConfig:
    return InputConfig(spei=path, dataset_name="synthetic", variable="spei")


def test_open_spei_rejects_duplicate_months(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.nc"
    write_spei(path, pd.DatetimeIndex(["2000-01-01", "2000-01-01"]))
    with pytest.raises(ValueError, match="strictly increasing monthly sequence"):
        open_spei(input_config(path), time_block_months=12)


def test_open_spei_rejects_missing_calendar_month(tmp_path: Path) -> None:
    path = tmp_path / "gap.nc"
    write_spei(path, pd.DatetimeIndex(["2000-01-01", "2000-03-01"]))
    with pytest.raises(ValueError, match="consecutive calendar months"):
        open_spei(input_config(path), time_block_months=12)


def test_open_spei_rejects_duplicate_longitudes(tmp_path: Path) -> None:
    path = tmp_path / "duplicate_lon.nc"
    values = np.zeros((2, 2, 3), dtype=np.float32)
    xr.Dataset(
        {"spei": (("time", "lat", "lon"), values)},
        coords={
            "time": pd.date_range("2000-01-01", periods=2, freq="MS"),
            "lat": [-0.5, 0.5],
            "lon": [0.0, 1.0, 1.0],
        },
    ).to_netcdf(path, engine="scipy")
    with pytest.raises(ValueError, match="longitude coordinates must be unique"):
        open_spei(input_config(path), time_block_months=12)


def test_open_spei_rejects_irregular_longitude_spacing(tmp_path: Path) -> None:
    path = tmp_path / "irregular_lon.nc"
    values = np.zeros((2, 2, 3), dtype=np.float32)
    xr.Dataset(
        {"spei": (("time", "lat", "lon"), values)},
        coords={
            "time": pd.date_range("2000-01-01", periods=2, freq="MS"),
            "lat": [-0.5, 0.5],
            "lon": [0.0, 1.0, 2.5],
        },
    ).to_netcdf(path, engine="scipy")
    with pytest.raises(ValueError, match="regularly spaced"):
        open_spei(input_config(path), time_block_months=12)


def test_read_target_grid_rejects_irregular_coordinates(tmp_path: Path) -> None:
    from spei3d.io import read_target_grid

    path = tmp_path / "target.nc"
    xr.Dataset(coords={"lat": [-0.5, 0.5], "lon": [0.0, 1.0, 2.5]}).to_netcdf(
        path, engine="scipy"
    )
    with pytest.raises(ValueError, match="longitude coordinates must be regularly spaced"):
        read_target_grid(path)
