"""Input normalization and optional event-label output."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import xarray as xr

from .config import InputConfig

_COORDINATE_ALIASES = {
    "latitude": "lat",
    "longitude": "lon",
    "valid_time": "time",
}


def open_spei(
    input_config: InputConfig, time_block_months: int
) -> tuple[xr.Dataset, xr.DataArray]:
    """Open a SPEI field and normalize it to ``time, lat, lon`` order."""

    path = input_config.spei
    if not path.exists():
        raise FileNotFoundError(f"SPEI input does not exist: {path}")
    chunks = {"time": int(time_block_months)} if importlib.util.find_spec("dask") else None
    dataset = xr.open_dataset(path, chunks=chunks)
    renames = {
        source: target
        for source, target in _COORDINATE_ALIASES.items()
        if source in dataset.dims and target not in dataset.dims
    }
    if renames:
        dataset = dataset.rename(renames)
    variable = input_config.variable
    if variable not in dataset.data_vars:
        candidates = [
            name
            for name, data in dataset.data_vars.items()
            if {"time", "lat", "lon"}.issubset(data.dims)
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"variable {variable!r} was not found and a unique 3-D variable "
                "could not be inferred"
            )
        variable = candidates[0]
    data = dataset[variable]
    if not {"time", "lat", "lon"}.issubset(data.dims):
        raise ValueError(f"SPEI variable dimensions must include time, lat, lon; got {data.dims}")
    data = data.transpose("time", "lat", "lon")
    if input_config.time_start or input_config.time_end:
        data = data.sel(time=slice(input_config.time_start, input_config.time_end))
    if data.sizes["time"] == 0:
        dataset.close()
        raise ValueError("the selected SPEI time window is empty")
    try:
        _validate_input_coordinates(data)
    except Exception:
        dataset.close()
        raise
    return dataset, data


def _validate_input_coordinates(data: xr.DataArray) -> None:
    """Validate the regular monthly coordinate contract used by the tracking engine."""

    _validate_spatial_coordinates(data["lat"].values, data["lon"].values)
    time_values = np.asarray(data["time"].values)
    if time_values.ndim != 1:
        raise ValueError("time coordinates must be one-dimensional")
    try:
        months = time_values.astype("datetime64[M]").astype(np.int64)
    except (TypeError, ValueError) as exc:
        raise ValueError("time coordinates must be decodable calendar dates") from exc
    month_steps = np.diff(months)
    if np.any(month_steps <= 0):
        raise ValueError("time coordinates must form a strictly increasing monthly sequence")
    if np.any(month_steps != 1):
        raise ValueError("time coordinates must represent consecutive calendar months")


def _validate_spatial_coordinates(
    latitude: np.ndarray, longitude: np.ndarray
) -> None:
    """Validate the one-dimensional regular grid required by area calculations."""

    for values_raw, label in (
        (latitude, "latitude"),
        (longitude, "longitude"),
    ):
        values = np.asarray(values_raw, dtype=np.float64)
        if values.ndim != 1:
            raise ValueError(f"{label} coordinates must be one-dimensional")
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{label} coordinates must be finite")
        if np.unique(values).size != values.size:
            raise ValueError(f"{label} coordinates must be unique")
        if values.size > 1:
            differences = np.diff(values)
            if not (np.all(differences > 0) or np.all(differences < 0)):
                raise ValueError(f"{label} coordinates must be strictly monotonic")
            spacing = np.abs(differences)
            if spacing.size > 1 and not np.allclose(
                spacing, spacing[0], rtol=1e-6, atol=1e-10
            ):
                raise ValueError(f"{label} coordinates must be regularly spaced")


def read_target_grid(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read latitude and longitude coordinates from a NetCDF target-grid file."""

    if not path.exists():
        raise FileNotFoundError(f"target-grid file does not exist: {path}")
    dataset = xr.open_dataset(path)
    renames = {
        source: target
        for source, target in _COORDINATE_ALIASES.items()
        if source in dataset.dims and target not in dataset.dims
    }
    if renames:
        dataset = dataset.rename(renames)
    try:
        latitude = np.asarray(dataset["lat"].values, dtype=np.float64)
        longitude = np.asarray(dataset["lon"].values, dtype=np.float64)
    finally:
        dataset.close()
    _validate_spatial_coordinates(latitude, longitude)
    return latitude, longitude


def prepare_for_interpolation(
    data: xr.DataArray,
    target_latitude: np.ndarray,
    target_longitude: np.ndarray,
) -> xr.DataArray:
    """Normalize longitude range and sort coordinates before interpolation."""

    source = data.transpose("time", "lat", "lon")
    source_longitude = np.asarray(source["lon"].values, dtype=np.float64)
    if np.nanmin(target_longitude) < 0 <= np.nanmin(source_longitude):
        source = source.assign_coords(lon=((source_longitude + 180.0) % 360.0) - 180.0)
    elif np.nanmin(target_longitude) >= 0 > np.nanmin(source_longitude):
        source = source.assign_coords(lon=np.mod(source_longitude, 360.0))
    source = source.sortby("lat").sortby("lon")
    longitude = np.asarray(source["lon"].values)
    _, unique_indices = np.unique(longitude, return_index=True)
    if unique_indices.size != longitude.size:
        source = source.isel(lon=np.sort(unique_indices))
    return source


def read_land_mask(
    path: Path | None,
    target_latitude: np.ndarray,
    target_longitude: np.ndarray,
) -> np.ndarray | None:
    """Read an optional Boolean land mask from NumPy or NetCDF format."""

    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"land-mask file does not exist: {path}")
    if path.suffix.lower() == ".npy":
        mask = np.load(path).astype(bool)
    else:
        dataset = xr.open_dataset(path)
        renames = {
            source: target
            for source, target in _COORDINATE_ALIASES.items()
            if source in dataset.dims and target not in dataset.dims
        }
        if renames:
            dataset = dataset.rename(renames)
        candidates = [
            name
            for name, data in dataset.data_vars.items()
            if {"lat", "lon"}.issubset(data.dims) and "time" not in data.dims
        ]
        if not candidates:
            dataset.close()
            raise ValueError("land-mask NetCDF must contain a two-dimensional lat-lon variable")
        data = dataset[candidates[0]].transpose("lat", "lon")
        data = data.sortby("lat").sortby("lon")
        data = data.interp(
            lat=xr.DataArray(target_latitude, dims="lat"),
            lon=xr.DataArray(target_longitude, dims="lon"),
            method="nearest",
        )
        mask = np.asarray(data.values > 0, dtype=bool)
        dataset.close()
    expected = (target_latitude.size, target_longitude.size)
    if mask.shape != expected:
        raise ValueError(f"land-mask shape {mask.shape} does not match target grid {expected}")
    return mask


class ZarrLabelWriter:
    """Minimal optional writer for a chunked event-label cube."""

    def __init__(
        self,
        path: Path,
        times: np.ndarray,
        latitude: np.ndarray,
        longitude: np.ndarray,
        time_chunk: int,
    ) -> None:
        try:
            import zarr
        except ImportError as exc:
            raise ImportError(
                "label output requires the optional 'labels' dependencies: "
                "pip install 'spei-3d-drought-object-tracking[labels]'"
            ) from exc
        self._zarr = zarr
        self.path = path
        group = zarr.open_group(str(path), mode="w")
        self.event_id = group.create_dataset(
            "event_id",
            shape=(times.size, latitude.size, longitude.size),
            chunks=(min(time_chunk, times.size), latitude.size, longitude.size),
            dtype="i4",
            fill_value=0,
            overwrite=True,
        )
        group.create_dataset("lat", data=np.asarray(latitude, dtype=np.float64), overwrite=True)
        group.create_dataset("lon", data=np.asarray(longitude, dtype=np.float64), overwrite=True)
        time_values = np.asarray(times).astype("datetime64[ns]").astype(np.int64)
        time_array = group.create_dataset("time", data=time_values, overwrite=True)
        time_array.attrs["units"] = "nanoseconds since 1970-01-01 00:00:00"

    def write(self, start: int, values: np.ndarray) -> None:
        self.event_id[start : start + values.shape[0]] = np.asarray(values, dtype=np.int32)

    def finalize(self, roots: np.ndarray, keep_ids: set[int], time_block: int) -> None:
        keep = np.zeros(roots.size, dtype=bool)
        if keep_ids:
            keep[np.asarray(sorted(keep_ids), dtype=np.int64)] = True
        for start in range(0, self.event_id.shape[0], time_block):
            stop = min(self.event_id.shape[0], start + time_block)
            raw = np.asarray(self.event_id[start:stop], dtype=np.int64)
            mapped = roots[np.clip(raw, 0, roots.size - 1)]
            mapped[(raw <= 0) | (~keep[mapped])] = 0
            self.event_id[start:stop] = mapped.astype(np.int32)
        self._zarr.consolidate_metadata(str(self.path))
