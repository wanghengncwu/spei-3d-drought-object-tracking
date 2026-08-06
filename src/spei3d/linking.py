"""Deterministic linking of monthly drought patches across adjacent months."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class LinkRule(str, Enum):
    MAXIMUM_OVERLAP = "maximum_overlap"
    OVERLAP_UNION = "overlap_union"
    MAXIMUM_IOU = "maximum_iou"


class UnionFind:
    """Union-find structure using the smallest object ID as canonical root."""

    def __init__(self) -> None:
        self.parent: list[int] = [0]

    def make(self) -> int:
        value = len(self.parent)
        self.parent.append(value)
        return value

    def find(self, value: int) -> int:
        parent = self.parent
        root = int(value)
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            next_value = parent[value]
            parent[value] = root
            value = next_value
        return root

    def union(self, values: np.ndarray | list[int]) -> tuple[int, int]:
        roots = sorted({self.find(int(value)) for value in values})
        if not roots:
            raise ValueError("cannot union an empty collection")
        canonical = roots[0]
        operations = 0
        for root in roots[1:]:
            if root != canonical:
                self.parent[root] = canonical
                operations += 1
        return canonical, operations

    def roots_array(self) -> np.ndarray:
        for value in range(1, len(self.parent)):
            self.parent[value] = self.find(value)
        return np.asarray(self.parent, dtype=np.int64)


@dataclass
class LinkState:
    previous_ids: np.ndarray
    union_find: UnionFind

    @classmethod
    def empty(cls, shape: tuple[int, ...]) -> LinkState:
        return cls(previous_ids=np.zeros(shape, dtype=np.int32), union_find=UnionFind())


@dataclass(frozen=True)
class LinkDiagnostics:
    patch_count: int
    new_patch_count: int
    linked_patch_count: int
    merge_patch_count: int
    split_parent_count: int
    union_operations: int


@dataclass(frozen=True)
class LinkResult:
    current_ids: np.ndarray
    patch_to_event: dict[int, int]
    diagnostics: LinkDiagnostics


def _canonicalize(ids: np.ndarray, union_find: UnionFind) -> np.ndarray:
    result = np.asarray(ids, dtype=np.int32).copy()
    nonzero = result > 0
    if np.any(nonzero):
        values = result[nonzero]
        result[nonzero] = np.fromiter(
            (union_find.find(int(value)) for value in values),
            dtype=np.int32,
            count=values.size,
        )
    return result


def link_month(
    state: LinkState,
    current_patches: np.ndarray,
    rule: LinkRule | str,
    minimum_overlap_cells: int = 1,
    minimum_iou: float = 0.10,
) -> LinkResult:
    """Link one labelled monthly patch field to the immediately preceding month.

    No temporal gaps are bridged. The function mutates ``state`` so it can be reused
    for the following month.
    """

    link_rule = LinkRule(rule)
    if minimum_overlap_cells < 1:
        raise ValueError("minimum_overlap_cells must be at least 1")
    if not 0 <= minimum_iou <= 1:
        raise ValueError("minimum_iou must be between 0 and 1")

    patches = np.asarray(current_patches, dtype=np.int32)
    if patches.shape != state.previous_ids.shape:
        raise ValueError("current_patches must match the previous grid shape")

    previous = _canonicalize(state.previous_ids, state.union_find)
    previous_sizes = np.bincount(previous.ravel())
    current_ids = np.zeros_like(patches, dtype=np.int32)
    patch_to_event: dict[int, int] = {}
    parent_to_children: dict[int, set[int]] = {}

    patch_ids, patch_counts = np.unique(patches[patches > 0], return_counts=True)
    order = [
        int(patch_id)
        for patch_id, _ in sorted(
            zip(patch_ids.tolist(), patch_counts.tolist(), strict=True),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    new_count = 0
    linked_count = 0
    merge_count = 0
    union_operations = 0

    for patch_id in order:
        patch_mask = patches == patch_id
        overlapping = previous[patch_mask]
        overlapping = overlapping[overlapping > 0]
        if overlapping.size:
            parents, overlaps = np.unique(overlapping, return_counts=True)
            eligible = overlaps >= int(minimum_overlap_cells)
            parents = parents[eligible].astype(np.int64)
            overlaps = overlaps[eligible].astype(np.int64)
        else:
            parents = np.empty(0, dtype=np.int64)
            overlaps = np.empty(0, dtype=np.int64)

        for parent in parents:
            parent_to_children.setdefault(int(parent), set()).add(patch_id)
        if parents.size > 1:
            merge_count += 1

        selected: int | None = None
        if parents.size and link_rule is LinkRule.MAXIMUM_OVERLAP:
            ranking = sorted(
                range(parents.size),
                key=lambda index: (-int(overlaps[index]), int(parents[index])),
            )
            selected = int(parents[ranking[0]])
        elif parents.size and link_rule is LinkRule.OVERLAP_UNION:
            selected, operations = state.union_find.union(parents.tolist())
            union_operations += operations
        elif parents.size and link_rule is LinkRule.MAXIMUM_IOU:
            patch_size = int(patch_mask.sum())
            iou = overlaps / (patch_size + previous_sizes[parents] - overlaps)
            valid_indices = np.flatnonzero(iou >= float(minimum_iou))
            if valid_indices.size:
                ranking = sorted(
                    valid_indices.tolist(),
                    key=lambda index: (
                        -float(iou[index]),
                        -int(overlaps[index]),
                        int(parents[index]),
                    ),
                )
                selected = int(parents[ranking[0]])

        if selected is None:
            selected = state.union_find.make()
            new_count += 1
        else:
            selected = state.union_find.find(selected)
            linked_count += 1
        current_ids[patch_mask] = selected
        patch_to_event[patch_id] = selected

    current_ids = _canonicalize(current_ids, state.union_find)
    patch_to_event = {
        patch_id: state.union_find.find(event_id)
        for patch_id, event_id in patch_to_event.items()
    }
    split_count = sum(len(children) > 1 for children in parent_to_children.values())
    state.previous_ids = current_ids
    return LinkResult(
        current_ids=current_ids,
        patch_to_event=patch_to_event,
        diagnostics=LinkDiagnostics(
            patch_count=len(order),
            new_patch_count=new_count,
            linked_patch_count=linked_count,
            merge_patch_count=merge_count,
            split_parent_count=split_count,
            union_operations=union_operations,
        ),
    )
