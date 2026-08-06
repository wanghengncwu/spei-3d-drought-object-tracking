import numpy as np

from spei3d.linking import LinkRule, LinkState, link_month


def state_with_previous(previous: np.ndarray) -> LinkState:
    state = LinkState.empty(previous.shape)
    for _ in range(int(previous.max())):
        state.union_find.make()
    state.previous_ids = previous.astype(np.int32)
    return state


def test_maximum_overlap_uses_smallest_parent_for_equal_overlap() -> None:
    previous = np.array([[1, 1, 0, 2, 2]], dtype=np.int32)
    patches = np.array([[1, 1, 1, 1, 1]], dtype=np.int32)
    result = link_month(
        state_with_previous(previous), patches, LinkRule.MAXIMUM_OVERLAP, 1, 0.0
    )
    assert np.all(result.current_ids == 1)
    assert result.diagnostics.merge_patch_count == 1


def test_split_daughters_inherit_same_parent_identity() -> None:
    previous = np.array([[1, 1, 1, 1, 1]], dtype=np.int32)
    patches = np.array([[1, 1, 0, 2, 2]], dtype=np.int32)
    result = link_month(
        state_with_previous(previous), patches, LinkRule.MAXIMUM_OVERLAP, 1, 0.0
    )
    assert set(result.current_ids[result.current_ids > 0]) == {1}
    assert result.diagnostics.split_parent_count == 1


def test_overlap_union_merges_parent_lineages() -> None:
    previous = np.array([[1, 1, 0, 2, 2]], dtype=np.int32)
    patches = np.array([[1, 1, 1, 1, 1]], dtype=np.int32)
    state = state_with_previous(previous)
    result = link_month(state, patches, LinkRule.OVERLAP_UNION, 1, 0.0)
    assert np.all(result.current_ids == 1)
    assert state.union_find.find(2) == 1
    assert result.diagnostics.union_operations == 1


def test_maximum_iou_starts_new_object_below_threshold() -> None:
    previous = np.array([[1, 1, 1, 1, 0]], dtype=np.int32)
    patches = np.array([[1, 0, 0, 0, 2]], dtype=np.int32)
    state = state_with_previous(previous)
    result = link_month(state, patches, LinkRule.MAXIMUM_IOU, 1, 0.5)
    object_ids = result.current_ids[result.current_ids > 0]
    assert object_ids.size == 2
    assert set(object_ids) == {2, 3}
    assert result.diagnostics.new_patch_count == 2
