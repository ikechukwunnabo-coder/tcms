"""Axis-compatible relationship payload parsing."""
from __future__ import annotations

from rest_framework import serializers


def parse_relation_pairs(payload, *, parent_key: str = "parent") -> list[tuple[int, int]]:
    """Normalise the relation payloads emitted by the Axis multiselect UI.

    Axis sends an array of ``[parent_id, child_id]`` pairs, sometimes wrapped in
    one extra array (``[[[...]]]``).  The compatibility API also accepts an
    object form and a list of objects so non-Axis clients can use it.
    """
    data = payload

    if isinstance(data, dict):
        parent = data.get(parent_key, data.get("parent", data.get("course", data.get("user"))))
        children = data.get("children", data.get("items", data.get("roles")))
        if parent is not None and isinstance(children, list):
            data = [[parent, child] for child in children]
        else:
            data = data.get("pairs", data.get("relations"))

    if not isinstance(data, list):
        raise serializers.ValidationError({"detail": "a list of relation pairs is required"})

    while (
        len(data) == 1
        and isinstance(data[0], list)
        and data[0]
        and isinstance(data[0][0], list)
    ):
        data = data[0]

    if not data:
        raise serializers.ValidationError({"detail": "at least one relation pair is required"})

    pairs: list[tuple[int, int]] = []
    for row in data:
        if isinstance(row, dict):
            parent = row.get(parent_key, row.get("parent", row.get("course", row.get("user"))))
            child = row.get("child", row.get("item", row.get("module", row.get("role"))))
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            parent, child = row[0], row[1]
        else:
            raise serializers.ValidationError(
                {"detail": "each relation must be a [parent_id, child_id] pair"}
            )
        try:
            pairs.append((int(parent), int(child)))
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError(
                {"detail": "relation IDs must be integers"}
            ) from exc

    return pairs
