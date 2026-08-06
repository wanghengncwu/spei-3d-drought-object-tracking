import numpy as np

from spei3d.catalogue import ObjectAccumulator, filter_catalogue, summarize_catalogue
from spei3d.linking import UnionFind
from spei3d.patches import PatchStats


def patch(patch_id: int, area: float, cat: float, deficit: float, minimum: float) -> PatchStats:
    return PatchStats(
        patch_id=patch_id,
        cell_count=int(area / 10),
        area_km2=area,
        catalogue_severity=cat,
        deficit_severity_km2months=deficit,
        minimum_spei=minimum,
    )


def test_accumulator_builds_event_and_monthly_metrics() -> None:
    accumulator = ObjectAccumulator(threshold=-1.0)
    accumulator.add(1, 0, np.datetime64("2000-01-01"), patch(1, 20, 3.5, 15, -2.0))
    accumulator.add(1, 1, np.datetime64("2000-02-01"), patch(1, 30, 2.0, 12, -1.8))
    accumulator.add(1, 1, np.datetime64("2000-02-01"), patch(2, 10, 1.2, 2, -1.2))
    union_find = UnionFind()
    union_find.make()
    events, monthly = accumulator.to_tables(union_find.roots_array())
    row = events.iloc[0]
    assert row["duration_months"] == 2
    assert row["active_months"] == 2
    assert row["AD_km2months"] == 60
    assert row["cumulative_catalogue_severity"] == 6.7
    assert row["threshold_deficit_severity_km2months"] == 29
    assert row["max_inst_area_km2"] == 30
    assert row["max_monthly_object_area_km2"] == 40
    assert np.isclose(row["mean_intensity_deficit"], 29 / 60)
    assert row["peak_intensity_deficit"] == 1.0
    assert len(monthly) == 2


def test_filter_catalogue_uses_duration_and_peak_area() -> None:
    accumulator = ObjectAccumulator(threshold=-1.0)
    accumulator.add(1, 0, np.datetime64("2000-01-01"), patch(1, 60, 1, 1, -1.1))
    accumulator.add(1, 1, np.datetime64("2000-02-01"), patch(1, 60, 1, 1, -1.1))
    accumulator.add(2, 0, np.datetime64("2000-01-01"), patch(2, 100, 1, 1, -1.1))
    union_find = UnionFind()
    union_find.make()
    union_find.make()
    events, monthly = accumulator.to_tables(union_find.roots_array())
    kept_events, kept_monthly = filter_catalogue(events, monthly, 2, 50)
    assert kept_events["event_id"].tolist() == [1]
    assert kept_monthly["event_id"].nunique() == 1


def test_summary_uses_ad_ranked_upper_decile() -> None:
    accumulator = ObjectAccumulator(threshold=-1.0)
    union_find = UnionFind()
    for event_id in range(1, 11):
        union_find.make()
        accumulator.add(
            event_id,
            event_id,
            np.datetime64("2000-01", "M") + np.timedelta64(event_id, "M"),
            patch(event_id, float(event_id), float(event_id * 2), 1.0, -1.1),
        )
    events, _ = accumulator.to_tables(union_find.roots_array())
    summary = summarize_catalogue(events)
    assert summary["object_count"] == 10
    assert summary["upper_decile_object_count"] == 1
    assert np.isclose(summary["upper_decile_AD_share"], 10 / 55)
    assert np.isclose(summary["upper_decile_catalogue_severity_share"], 20 / 110)
