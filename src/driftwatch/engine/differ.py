"""State diffing engine that compares snapshots and identifies drift."""

from __future__ import annotations

from typing import Any

from driftwatch.models import (
    ChangeType,
    DiffResult,
    Resource,
    ResourceChange,
    Snapshot,
)


class StateDiffer:
    """Compares two snapshots and produces a structured diff."""

    def diff(self, before: Snapshot, after: Snapshot) -> DiffResult:
        before_map = {r.id: r for r in before.resources}
        after_map = {r.id: r for r in after.resources}

        changes: list[ResourceChange] = []

        # Detect added resources
        for rid in sorted(set(after_map) - set(before_map)):
            changes.append(
                ResourceChange(
                    resource_id=rid,
                    change_type=ChangeType.ADDED,
                )
            )

        # Detect removed resources
        for rid in sorted(set(before_map) - set(after_map)):
            changes.append(
                ResourceChange(
                    resource_id=rid,
                    change_type=ChangeType.REMOVED,
                )
            )

        # Detect modified resources
        common_ids = sorted(set(before_map) & set(after_map))
        for rid in common_ids:
            field_changes = self._diff_resource(before_map[rid], after_map[rid])
            changes.extend(field_changes)

        return DiffResult(
            snapshot_before_id=before.id,
            snapshot_after_id=after.id,
            changes=tuple(changes),
        )

    def _diff_resource(self, before: Resource, after: Resource) -> list[ResourceChange]:
        raw_changes = _diff_dicts(before.properties, after.properties)
        changes: list[ResourceChange] = []

        for path, old_val, new_val, kind in raw_changes:
            if kind == "changed":
                changes.append(
                    ResourceChange(
                        resource_id=before.id,
                        change_type=ChangeType.MODIFIED,
                        field_path=path,
                        old_value=old_val,
                        new_value=new_val,
                    )
                )
            elif kind == "added":
                changes.append(
                    ResourceChange(
                        resource_id=before.id,
                        change_type=ChangeType.MODIFIED,
                        field_path=f"{path} (added)",
                    )
                )
            elif kind == "removed":
                changes.append(
                    ResourceChange(
                        resource_id=before.id,
                        change_type=ChangeType.MODIFIED,
                        field_path=f"{path} (removed)",
                    )
                )

        return changes


def _diff_dicts(
    old: dict[str, Any], new: dict[str, Any], prefix: str = ""
) -> list[tuple[str, Any, Any, str]]:
    """Recursively diff two dicts, returning (path, old, new, kind) tuples."""
    changes: list[tuple[str, Any, Any, str]] = []

    all_keys = sorted(set(old) | set(new))
    for key in all_keys:
        path = f"{prefix}.{key}" if prefix else key
        if key not in old:
            changes.append((path, None, new[key], "added"))
        elif key not in new:
            changes.append((path, old[key], None, "removed"))
        elif old[key] != new[key]:
            if isinstance(old[key], dict) and isinstance(new[key], dict):
                changes.extend(_diff_dicts(old[key], new[key], path))
            else:
                changes.append((path, old[key], new[key], "changed"))

    return changes
