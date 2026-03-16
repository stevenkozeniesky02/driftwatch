"""Anomaly detection for infrastructure drift."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from driftwatch.models import (
    Anomaly,
    ChangeType,
    DiffResult,
    DriftSeverity,
    Snapshot,
)

# Thresholds
_HIGH_CHANGE_RATE = 0.25  # >25% resources changed
_SECURITY_KEYWORDS = {"security_group", "iam", "policy", "role", "permission", "firewall"}
_UNEXPECTED_WINDOW_HOURS = 8  # Changes outside business hours (22:00-06:00)


class AnomalyDetector:
    """Detects anomalies by analyzing drift patterns across snapshots."""

    def analyze(self, diffs: list[DiffResult], snapshots: list[Snapshot]) -> list[Anomaly]:
        anomalies: list[Anomaly] = []
        for diff in diffs:
            anomalies.extend(self._check_high_change_rate(diff, snapshots))
            anomalies.extend(self._check_security_drift(diff))
            anomalies.extend(self._check_unexpected_resources(diff))
            anomalies.extend(self._check_off_hours_changes(diff))
        anomalies.extend(self._check_churn(diffs))
        return anomalies

    def _check_high_change_rate(
        self, diff: DiffResult, snapshots: list[Snapshot]
    ) -> list[Anomaly]:
        snap_map = {s.id: s for s in snapshots}
        before_snap = snap_map.get(diff.snapshot_before_id)
        if not before_snap or len(before_snap.resources) == 0:
            return []
        change_rate = len(diff.changes) / len(before_snap.resources)
        if change_rate > _HIGH_CHANGE_RATE:
            return [
                Anomaly(
                    resource_id="*",
                    description=(
                        f"High change rate detected: {change_rate:.0%} of resources changed "
                        f"({len(diff.changes)}/{len(before_snap.resources)})"
                    ),
                    severity=DriftSeverity.HIGH,
                )
            ]
        return []

    def _check_security_drift(self, diff: DiffResult) -> list[Anomaly]:
        anomalies = []
        for change in diff.changes:
            resource_lower = change.resource_id.lower()
            is_security = any(kw in resource_lower for kw in _SECURITY_KEYWORDS)
            if is_security and change.change_type in (ChangeType.MODIFIED, ChangeType.ADDED):
                severity = DriftSeverity.CRITICAL if change.change_type == ChangeType.MODIFIED else DriftSeverity.HIGH
                anomalies.append(
                    Anomaly(
                        resource_id=change.resource_id,
                        description=f"Security-related resource {change.change_type.value}: {change.resource_id}",
                        severity=severity,
                    )
                )
        return anomalies

    def _check_unexpected_resources(self, diff: DiffResult) -> list[Anomaly]:
        anomalies = []
        for change in diff.added:
            if "mystery" in change.resource_id.lower() or "unknown" in change.resource_id.lower():
                anomalies.append(
                    Anomaly(
                        resource_id=change.resource_id,
                        description=f"Unexpected resource appeared: {change.resource_id}",
                        severity=DriftSeverity.HIGH,
                    )
                )
            else:
                anomalies.append(
                    Anomaly(
                        resource_id=change.resource_id,
                        description=f"New resource detected: {change.resource_id}",
                        severity=DriftSeverity.MEDIUM,
                    )
                )
        for change in diff.removed:
            anomalies.append(
                Anomaly(
                    resource_id=change.resource_id,
                    description=f"Resource disappeared: {change.resource_id}",
                    severity=DriftSeverity.HIGH,
                )
            )
        return anomalies

    def _check_off_hours_changes(self, diff: DiffResult) -> list[Anomaly]:
        hour = diff.timestamp.hour
        if (hour >= 22 or hour < 6) and len(diff.changes) > 0:
            return [
                Anomaly(
                    resource_id="*",
                    description=f"Infrastructure changes detected at {diff.timestamp.strftime('%H:%M UTC')} (off-hours)",
                    severity=DriftSeverity.MEDIUM,
                )
            ]
        return []

    def _check_churn(self, diffs: list[DiffResult]) -> list[Anomaly]:
        """Flag resources that change too frequently (churn)."""
        if len(diffs) < 3:
            return []
        resource_change_count: Counter[str] = Counter()
        for diff in diffs:
            for change in diff.changes:
                resource_change_count[change.resource_id] += 1

        anomalies = []
        for rid, count in resource_change_count.most_common():
            if count >= 3:
                anomalies.append(
                    Anomaly(
                        resource_id=rid,
                        description=f"Resource churning: changed {count} times in recent history",
                        severity=DriftSeverity.MEDIUM,
                    )
                )
        return anomalies
