"""Streaming three-dimensional drought-object extraction engine."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import time
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from . import ALGORITHM_VERSION, SOFTWARE_NAME, SOFTWARE_TITLE, __version__
from .catalogue import (
    ObjectAccumulator,
    annual_active_year_summary,
    filter_catalogue,
    summarize_catalogue,
)
from .config import ProjectConfig
from .geo import cell_area_by_lat_km2
from .io import (
    ZarrLabelWriter,
    open_spei,
    prepare_for_interpolation,
    read_land_mask,
    read_target_grid,
)
from .linking import LinkRule, LinkState, link_month
from .patches import filter_monthly_patches, label_month, patch_statistics


@dataclass(frozen=True)
class RunSummary:
    output_dir: Path
    object_count: int
    raw_object_count: int
    total_AD_km2months: float
    total_catalogue_severity: float
    upper_decile_AD_share: float
    upper_decile_catalogue_severity_share: float


def run_extraction(config: ProjectConfig, output_dir: Path | None = None) -> RunSummary:
    """Run one drought-object extraction from a validated project configuration."""

    output = Path(output_dir or config.output.root)
    _prepare_output(output, config.runtime.overwrite)
    started = time.time()
    dataset, source = open_spei(config.input, config.runtime.time_block_months)
    try:
        if config.input.target_grid is None:
            latitude = np.asarray(source["lat"].values, dtype=np.float64)
            longitude = np.asarray(source["lon"].values, dtype=np.float64)
            needs_regridding = False
        else:
            latitude, longitude = read_target_grid(config.input.target_grid)
            source = prepare_for_interpolation(source, latitude, longitude)
            needs_regridding = not (
                source.sizes["lat"] == latitude.size
                and source.sizes["lon"] == longitude.size
                and np.allclose(source["lat"].values, latitude)
                and np.allclose(source["lon"].values, longitude)
            )
        times = np.asarray(source["time"].values)
        mask = read_land_mask(config.input.land_mask, latitude, longitude)
        row_area = cell_area_by_lat_km2(latitude, longitude)
        state = LinkState.empty((latitude.size, longitude.size))
        accumulator = ObjectAccumulator(config.event_definition.spei_threshold)
        diagnostics_rows: list[dict[str, Any]] = []

        label_writer = None
        if config.runtime.write_labels:
            label_writer = ZarrLabelWriter(
                output / "events_3d.zarr",
                times,
                latitude,
                longitude,
                config.runtime.time_block_months,
            )

        for block_start in range(0, times.size, config.runtime.time_block_months):
            block_stop = min(times.size, block_start + config.runtime.time_block_months)
            block = source.isel(time=slice(block_start, block_stop))
            if needs_regridding:
                block = block.interp(
                    lat=xr.DataArray(latitude, dims="lat"),
                    lon=xr.DataArray(longitude, dims="lon"),
                    method="linear",
                )
            values = np.asarray(block.values, dtype=np.float32)
            labels_block = np.zeros(
                (block_stop - block_start, latitude.size, longitude.size),
                dtype=np.int32,
            )
            for local_index, spei_month in enumerate(values):
                time_index = block_start + local_index
                drought = np.isfinite(spei_month) & (
                    spei_month <= config.event_definition.spei_threshold
                )
                if mask is not None:
                    drought &= mask
                patches = label_month(drought, config.event_definition.connectivity)
                patches = filter_monthly_patches(
                    patches,
                    row_area,
                    config.event_definition.minimum_monthly_patch_area_km2,
                )
                result = link_month(
                    state,
                    patches,
                    LinkRule(config.linking.rule),
                    config.linking.minimum_overlap_cells,
                    config.linking.minimum_iou,
                )
                statistics = patch_statistics(
                    patches,
                    spei_month,
                    row_area,
                    config.event_definition.spei_threshold,
                )
                for patch_id, event_id in result.patch_to_event.items():
                    accumulator.add(
                        event_id,
                        time_index,
                        times[time_index],
                        statistics[patch_id],
                    )
                diagnostics_rows.append(
                    {
                        "time_index": time_index,
                        "time": _time_string(times[time_index]),
                        **asdict(result.diagnostics),
                    }
                )
                labels_block[local_index] = result.current_ids
            if label_writer is not None:
                label_writer.write(block_start, labels_block)

        roots = state.union_find.roots_array()
        raw_events, raw_monthly = accumulator.to_tables(roots)
        events, monthly = filter_catalogue(
            raw_events,
            raw_monthly,
            config.event_definition.minimum_duration_months,
            config.event_definition.minimum_peak_area_km2,
        )
        annual = _annual_with_onsets(events, annual_active_year_summary(monthly))
        diagnostics = pd.DataFrame(diagnostics_rows)
        catalogue_summary = summarize_catalogue(events)

        raw_events.to_csv(output / "raw_events_table.csv", index=False)
        events.to_csv(output / "events_table.csv", index=False)
        monthly.to_csv(output / "event_monthly_stats.csv", index=False)
        annual.to_csv(output / "annual_active_year_summary.csv", index=False)
        diagnostics.to_csv(output / "link_diagnostics_monthly.csv", index=False)

        keep_ids = set(events["event_id"].astype(int))
        if label_writer is not None:
            label_writer.finalize(roots, keep_ids, config.runtime.time_block_months)

        manifest = {
            "software": {
                "name": SOFTWARE_NAME,
                "title": SOFTWARE_TITLE,
                "version": __version__,
                "algorithm_version": ALGORITHM_VERSION,
            },
            "dependencies": _dependency_versions(),
            "dataset_name": config.input.dataset_name,
            "input": {
                "spei": _file_descriptor(
                    config.input.spei, include_hash=config.runtime.hash_inputs
                ),
                "variable": config.input.variable,
                "time_start": config.input.time_start,
                "time_end": config.input.time_end,
                "target_grid": (
                    _file_descriptor(
                        config.input.target_grid, include_hash=config.runtime.hash_inputs
                    )
                    if config.input.target_grid
                    else None
                ),
                "land_mask": (
                    _file_descriptor(
                        config.input.land_mask, include_hash=config.runtime.hash_inputs
                    )
                    if config.input.land_mask
                    else None
                ),
            },
            "coverage": {
                "start_time": _time_string(times[0]),
                "end_time": _time_string(times[-1]),
            },
            "event_definition": asdict(config.event_definition),
            "linking": asdict(config.linking),
            "grid": {
                "n_time": int(times.size),
                "n_lat": int(latitude.size),
                "n_lon": int(longitude.size),
                "latitude_min": float(np.min(latitude)),
                "latitude_max": float(np.max(latitude)),
                "longitude_min": float(np.min(longitude)),
                "longitude_max": float(np.max(longitude)),
            },
            "counts": {
                "raw_objects": int(raw_events.shape[0]),
                "retained_objects": int(events.shape[0]),
                "merge_patch_months": int(diagnostics["merge_patch_count"].sum()),
                "split_parent_months": int(diagnostics["split_parent_count"].sum()),
                "union_operations": int(diagnostics["union_operations"].sum()),
            },
            "catalogue_summary": _json_safe(catalogue_summary),
            "runtime_seconds": time.time() - started,
        }
        (output / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        (output / "run.ok").write_text("OK\n", encoding="ascii")
        return RunSummary(
            output_dir=output,
            object_count=int(events.shape[0]),
            raw_object_count=int(raw_events.shape[0]),
            total_AD_km2months=float(catalogue_summary["total_AD_km2months"]),
            total_catalogue_severity=float(catalogue_summary["total_catalogue_severity"]),
            upper_decile_AD_share=float(catalogue_summary["upper_decile_AD_share"]),
            upper_decile_catalogue_severity_share=float(
                catalogue_summary["upper_decile_catalogue_severity_share"]
            ),
        )
    finally:
        dataset.close()


def _prepare_output(output: Path, overwrite: bool) -> None:
    if output.exists() and any(output.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"output directory is not empty: {output}; "
                "set runtime.overwrite: true to replace it"
            )
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def _annual_with_onsets(events: pd.DataFrame, annual: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        result = annual.copy()
        result["onset_object_count"] = pd.Series(dtype="int64")
        return result
    onset = (
        pd.to_datetime(events["start_time"])
        .dt.year.value_counts()
        .rename_axis("year")
        .rename("onset_object_count")
        .reset_index()
    )
    if annual.empty:
        return onset.sort_values("year").reset_index(drop=True)
    result = annual.merge(onset, on="year", how="outer").sort_values("year")
    result["onset_object_count"] = result["onset_object_count"].fillna(0).astype(int)
    return result.reset_index(drop=True)


def _time_string(value: Any) -> str:
    try:
        return np.datetime_as_string(np.datetime64(value), unit="D")
    except (TypeError, ValueError):
        return str(value)[:10]


def _json_safe(mapping: dict[str, float | int]) -> dict[str, float | int | None]:
    output: dict[str, float | int | None] = {}
    for key, value in mapping.items():
        if isinstance(value, float) and not np.isfinite(value):
            output[key] = None
        else:
            output[key] = value
    return output


def _file_descriptor(
    path: Path, *, include_hash: bool = False
) -> dict[str, str | int]:
    stat = path.stat()
    descriptor: dict[str, str | int] = {
        "name": path.name,
        "size_bytes": int(stat.st_size),
    }
    if include_hash:
        descriptor["sha256"] = _sha256(path)
    return descriptor


def _sha256(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _dependency_versions() -> dict[str, str]:
    packages = {
        "numpy": "numpy",
        "pandas": "pandas",
        "xarray": "xarray",
        "scipy": "scipy",
        "pyyaml": "PyYAML",
        "netcdf4": "netCDF4",
    }
    versions = {"python": platform.python_version()}
    for key, distribution in packages.items():
        try:
            versions[key] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            versions[key] = "not-installed"
    return versions
