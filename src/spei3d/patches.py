"""Monthly drought-patch labelling, filtering, and metrics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class PatchStats:
    patch_id: int
    cell_count: int
    area_km2: float
    catalogue_severity: float
    deficit_severity_km2months: float
    minimum_spei: float


def label_month(mask: np.ndarray, connectivity: int = 8) -> np.ndarray:
    """Label connected drought cells in one monthly field."""

    if connectivity == 8:
        structure = np.ones((3, 3), dtype=np.uint8)
    elif connectivity == 4:
        structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8)
    else:
        raise ValueError("connectivity must be 4 or 8")
    labels, _ = ndimage.label(np.asarray(mask, dtype=bool), structure=structure)
    return labels.astype(np.int32)


def filter_monthly_patches(
    labels: np.ndarray,
    row_area_km2: np.ndarray,
    minimum_area_km2: float,
) -> np.ndarray:
    """Remove monthly patches whose area is below the configured threshold."""

    result = np.asarray(labels, dtype=np.int32).copy()
    if minimum_area_km2 <= 0 or result.max(initial=0) == 0:
        return result
    row_area = np.asarray(row_area_km2, dtype=np.float64)
    if row_area.shape != (result.shape[0],):
        raise ValueError("row_area_km2 must contain one value per latitude row")
    maximum = int(result.max())
    areas = np.zeros(maximum + 1, dtype=np.float64)
    for row_index, cell_area in enumerate(row_area):
        areas += np.bincount(result[row_index], minlength=maximum + 1) * cell_area
    keep = areas >= float(minimum_area_km2)
    keep[0] = False
    result[~keep[result]] = 0
    return result


def patch_statistics(
    labels: np.ndarray,
    spei: np.ndarray,
    row_area_km2: np.ndarray,
    threshold: float,
) -> dict[int, PatchStats]:
    """Calculate monthly metrics for all non-zero patch labels."""

    labels_array = np.asarray(labels, dtype=np.int32)
    spei_array = np.asarray(spei, dtype=np.float64)
    row_area = np.asarray(row_area_km2, dtype=np.float64)
    if labels_array.shape != spei_array.shape:
        raise ValueError("labels and spei must have identical shapes")
    if row_area.shape != (labels_array.shape[0],):
        raise ValueError("row_area_km2 must contain one value per latitude row")

    output: dict[int, PatchStats] = {}
    for patch_id in np.unique(labels_array):
        if patch_id == 0:
            continue
        mask = labels_array == patch_id
        row_counts = mask.sum(axis=1, dtype=np.int64)
        area = float(np.dot(row_counts, row_area))
        values = spei_array[mask]
        finite = np.isfinite(values)
        values = values[finite]
        row_indices, _ = np.where(mask)
        weights = row_area[row_indices][finite]
        deficits = np.maximum(0.0, float(threshold) - values)
        output[int(patch_id)] = PatchStats(
            patch_id=int(patch_id),
            cell_count=int(values.size),
            area_km2=area,
            catalogue_severity=float(-values.sum()),
            deficit_severity_km2months=float(np.dot(deficits, weights)),
            minimum_spei=float(values.min()) if values.size else float("nan"),
        )
    return output
