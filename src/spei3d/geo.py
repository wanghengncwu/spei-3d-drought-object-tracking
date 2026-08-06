"""Geographic grid calculations used by the extraction engine."""

from __future__ import annotations

import math

import numpy as np


def cell_area_by_lat_km2(
    latitude: np.ndarray,
    longitude: np.ndarray,
    earth_radius_km: float = 6371.0,
) -> np.ndarray:
    """Return one grid-cell area per latitude row for a regular lon-lat grid."""

    lat = np.asarray(latitude, dtype=np.float64)
    lon = np.asarray(longitude, dtype=np.float64)
    if lat.ndim != 1 or lon.ndim != 1:
        raise ValueError("latitude and longitude must be one-dimensional")
    if lat.size == 0 or lon.size < 2:
        raise ValueError("at least one latitude and two longitudes are required")
    delta_lon = math.radians(float(np.median(np.abs(np.diff(lon)))))
    edges = np.empty(lat.size + 1, dtype=np.float64)
    if lat.size == 1:
        half_width = 0.5
        edges[:] = [lat[0] - half_width, lat[0] + half_width]
    else:
        edges[1:-1] = 0.5 * (lat[:-1] + lat[1:])
        edges[0] = lat[0] - (edges[1] - lat[0])
        edges[-1] = lat[-1] + (lat[-1] - edges[-2])
    edges = np.clip(edges, -90.0, 90.0)
    latitude_band = np.abs(
        np.sin(np.radians(edges[1:])) - np.sin(np.radians(edges[:-1]))
    )
    return (earth_radius_km**2 * delta_lon * latitude_band).astype(np.float64)
