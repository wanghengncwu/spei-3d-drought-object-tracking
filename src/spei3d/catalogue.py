"""Event-level accumulation, filtering, and catalogue summaries."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .patches import PatchStats


@dataclass
class _MonthlyAggregate:
    event_id: int
    time_index: int
    time: Any
    area_km2: float = 0.0
    catalogue_severity: float = 0.0
    deficit_severity_km2months: float = 0.0
    gridcell_count: int = 0
    maximum_patch_area_km2: float = 0.0
    minimum_spei: float = float("inf")

    def add_patch(self, stats: PatchStats) -> None:
        self.area_km2 += stats.area_km2
        self.catalogue_severity += stats.catalogue_severity
        self.deficit_severity_km2months += stats.deficit_severity_km2months
        self.gridcell_count += stats.cell_count
        self.maximum_patch_area_km2 = max(self.maximum_patch_area_km2, stats.area_km2)
        self.minimum_spei = min(self.minimum_spei, stats.minimum_spei)

    def combine(self, other: _MonthlyAggregate) -> None:
        self.area_km2 += other.area_km2
        self.catalogue_severity += other.catalogue_severity
        self.deficit_severity_km2months += other.deficit_severity_km2months
        self.gridcell_count += other.gridcell_count
        self.maximum_patch_area_km2 = max(
            self.maximum_patch_area_km2, other.maximum_patch_area_km2
        )
        self.minimum_spei = min(self.minimum_spei, other.minimum_spei)


class ObjectAccumulator:
    """Accumulate patch metrics before final canonical event IDs are known."""

    def __init__(self, threshold: float) -> None:
        self.threshold = float(threshold)
        self._records: dict[tuple[int, int], _MonthlyAggregate] = {}

    def add(
        self,
        event_id: int,
        time_index: int,
        time_value: Any,
        patch_stats: PatchStats,
    ) -> None:
        key = (int(event_id), int(time_index))
        aggregate = self._records.get(key)
        if aggregate is None:
            aggregate = _MonthlyAggregate(
                event_id=int(event_id),
                time_index=int(time_index),
                time=time_value,
            )
            self._records[key] = aggregate
        aggregate.add_patch(patch_stats)

    def to_tables(self, roots: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Collapse unioned IDs and return event-level and monthly tables."""

        canonical: dict[tuple[int, int], _MonthlyAggregate] = {}
        for (event_id, time_index), record in self._records.items():
            if event_id >= roots.size:
                raise ValueError(f"missing union-find root for event ID {event_id}")
            root = int(roots[event_id])
            key = (root, time_index)
            if key not in canonical:
                canonical[key] = _MonthlyAggregate(
                    event_id=root,
                    time_index=time_index,
                    time=record.time,
                )
            canonical[key].combine(record)

        monthly_rows: list[dict[str, Any]] = []
        for (event_id, time_index), record in sorted(canonical.items()):
            monthly_rows.append(
                {
                    "event_id": event_id,
                    "time_index": time_index,
                    "time": _time_string(record.time),
                    "area_km2": record.area_km2,
                    "catalogue_severity": record.catalogue_severity,
                    "threshold_deficit_severity_km2months": (
                        record.deficit_severity_km2months
                    ),
                    "gridcell_count": record.gridcell_count,
                    "maximum_patch_area_km2": record.maximum_patch_area_km2,
                    "minimum_spei": record.minimum_spei,
                }
            )
        monthly = pd.DataFrame(monthly_rows)
        if monthly.empty:
            return _empty_events(), monthly

        event_rows: list[dict[str, Any]] = []
        for event_id, group in monthly.groupby("event_id", sort=True):
            group = group.sort_values("time_index")
            start_index = int(group["time_index"].min())
            end_index = int(group["time_index"].max())
            area_duration = float(group["area_km2"].sum())
            deficit_severity = float(
                group["threshold_deficit_severity_km2months"].sum()
            )
            minimum_spei = float(group["minimum_spei"].min())
            event_rows.append(
                {
                    "event_id": int(event_id),
                    "start_time": str(group.iloc[0]["time"]),
                    "end_time": str(group.iloc[-1]["time"]),
                    "duration_months": end_index - start_index + 1,
                    "active_months": int(group.shape[0]),
                    "AD_km2months": area_duration,
                    "cumulative_catalogue_severity": float(
                        group["catalogue_severity"].sum()
                    ),
                    "threshold_deficit_severity_km2months": deficit_severity,
                    "mean_intensity_deficit": (
                        deficit_severity / area_duration if area_duration > 0 else float("nan")
                    ),
                    "peak_intensity_deficit": max(0.0, self.threshold - minimum_spei),
                    "gridcell_months": int(group["gridcell_count"].sum()),
                    "max_inst_area_km2": float(group["maximum_patch_area_km2"].max()),
                    "max_monthly_object_area_km2": float(group["area_km2"].max()),
                }
            )
        events = pd.DataFrame(event_rows).sort_values("event_id").reset_index(drop=True)
        return events, monthly.reset_index(drop=True)


def filter_catalogue(
    events: pd.DataFrame,
    monthly: pd.DataFrame,
    minimum_duration_months: int,
    minimum_peak_area_km2: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the event-duration and peak-area filters used for the retained catalogue."""

    if events.empty:
        return events.copy(), monthly.iloc[0:0].copy()
    keep = events[
        (events["duration_months"] >= int(minimum_duration_months))
        & (events["max_inst_area_km2"] >= float(minimum_peak_area_km2))
    ].copy()
    keep_ids = set(keep["event_id"].astype(int))
    kept_monthly = monthly[monthly["event_id"].isin(keep_ids)].copy()
    return keep.reset_index(drop=True), kept_monthly.reset_index(drop=True)


def annual_active_year_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate retained monthly object metrics by the year in which they occurred."""

    columns = [
        "year",
        "active_object_count",
        "AD_km2months",
        "cumulative_catalogue_severity",
        "threshold_deficit_severity_km2months",
    ]
    if monthly.empty:
        return pd.DataFrame(columns=columns)
    data = monthly.copy()
    data["year"] = pd.to_datetime(data["time"]).dt.year
    result = data.groupby("year", as_index=False).agg(
        active_object_count=("event_id", "nunique"),
        AD_km2months=("area_km2", "sum"),
        cumulative_catalogue_severity=("catalogue_severity", "sum"),
        threshold_deficit_severity_km2months=(
            "threshold_deficit_severity_km2months",
            "sum",
        ),
    )
    return result[columns]


def summarize_catalogue(events: pd.DataFrame) -> dict[str, float | int]:
    """Return core totals and AD-ranked upper-decile concentration metrics."""

    if events.empty:
        return {
            "object_count": 0,
            "upper_decile_object_count": 0,
            "total_AD_km2months": 0.0,
            "total_catalogue_severity": 0.0,
            "upper_decile_AD_share": float("nan"),
            "upper_decile_catalogue_severity_share": float("nan"),
        }
    count = int(events.shape[0])
    upper_count = max(1, int(math.ceil(0.10 * count)))
    ranked = events.sort_values(
        ["AD_km2months", "event_id"], ascending=[False, True]
    ).head(upper_count)
    total_ad = float(events["AD_km2months"].sum())
    total_severity = float(events["cumulative_catalogue_severity"].sum())
    return {
        "object_count": count,
        "upper_decile_object_count": upper_count,
        "total_AD_km2months": total_ad,
        "total_catalogue_severity": total_severity,
        "upper_decile_AD_share": (
            float(ranked["AD_km2months"].sum()) / total_ad
            if total_ad > 0
            else float("nan")
        ),
        "upper_decile_catalogue_severity_share": (
            float(ranked["cumulative_catalogue_severity"].sum()) / total_severity
            if total_severity > 0
            else float("nan")
        ),
    }


def _time_string(value: Any) -> str:
    try:
        return np.datetime_as_string(np.datetime64(value), unit="D")
    except (TypeError, ValueError):
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)[:10]


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "event_id",
            "start_time",
            "end_time",
            "duration_months",
            "active_months",
            "AD_km2months",
            "cumulative_catalogue_severity",
            "threshold_deficit_severity_km2months",
            "mean_intensity_deficit",
            "peak_intensity_deficit",
            "gridcell_months",
            "max_inst_area_km2",
            "max_monthly_object_area_km2",
        ]
    )
