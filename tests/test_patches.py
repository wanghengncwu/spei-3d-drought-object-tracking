import numpy as np

from spei3d.geo import cell_area_by_lat_km2
from spei3d.patches import filter_monthly_patches, label_month, patch_statistics


def test_diagonal_cells_are_connected_only_with_eight_neighbours() -> None:
    mask = np.array([[True, False], [False, True]])
    assert label_month(mask, connectivity=8).max() == 1
    assert label_month(mask, connectivity=4).max() == 2


def test_area_filter_removes_only_patch_below_threshold() -> None:
    labels = np.array([[1, 1, 0], [0, 2, 0]], dtype=np.int32)
    row_area = np.array([10.0, 10.0])
    filtered = filter_monthly_patches(labels, row_area, minimum_area_km2=15.0)
    expected = np.array([[1, 1, 0], [0, 0, 0]], dtype=np.int32)
    assert np.array_equal(filtered, expected)


def test_patch_statistics_returns_area_and_severity_metrics() -> None:
    labels = np.array([[1, 1], [0, 2]], dtype=np.int32)
    spei = np.array([[-1.5, -2.0], [0.0, -1.2]])
    row_area = np.array([10.0, 20.0])
    stats = patch_statistics(labels, spei, row_area, threshold=-1.0)
    assert stats[1].area_km2 == 20.0
    assert stats[1].catalogue_severity == 3.5
    assert stats[1].deficit_severity_km2months == 15.0
    assert stats[2].area_km2 == 20.0
    assert stats[2].catalogue_severity == 1.2
    assert np.isclose(stats[2].deficit_severity_km2months, 4.0)


def test_cell_area_is_positive_and_symmetric_about_equator() -> None:
    area = cell_area_by_lat_km2(np.array([-0.5, 0.5]), np.array([0.0, 1.0, 2.0]))
    assert np.all(area > 0)
    assert np.isclose(area[0], area[1])
