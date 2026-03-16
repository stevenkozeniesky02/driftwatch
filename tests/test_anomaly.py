"""Tests for anomaly detection."""

from datetime import datetime, timezone

from driftwatch.engine.anomaly import AnomalyDetector
from driftwatch.engine.differ import StateDiffer
from driftwatch.models import (
    ChangeType,
    DiffResult,
    DriftSeverity,
    Resource,
    ResourceChange,
    Snapshot,
)


class TestAnomalyDetector:
    def test_high_change_rate(self, sample_snapshot, drifted_snapshot):
        differ = StateDiffer()
        diff = differ.diff(sample_snapshot, drifted_snapshot)
        detector = AnomalyDetector()
        anomalies = detector.analyze([diff], [sample_snapshot, drifted_snapshot])

        high_rate = [a for a in anomalies if "change rate" in a.description.lower()]
        assert len(high_rate) > 0
        assert high_rate[0].severity == DriftSeverity.HIGH

    def test_security_drift_detected(self):
        changes = (
            ResourceChange(
                resource_id="aws/security_group/sg-web",
                change_type=ChangeType.MODIFIED,
                field_path="ingress_rules",
                old_value=3,
                new_value=8,
            ),
        )
        diff = DiffResult(
            snapshot_before_id="s1",
            snapshot_after_id="s2",
            changes=changes,
        )
        snap = Snapshot.create([
            Resource(type="security_group", name="sg-web", provider="aws",
                     properties={"ingress_rules": 3}),
        ])
        detector = AnomalyDetector()
        anomalies = detector.analyze([diff], [snap])
        security = [a for a in anomalies if "security" in a.description.lower()]
        assert len(security) > 0
        assert security[0].severity == DriftSeverity.CRITICAL

    def test_unexpected_resource_detected(self):
        changes = (
            ResourceChange(
                resource_id="aws/ec2_instance/mystery-server",
                change_type=ChangeType.ADDED,
            ),
        )
        diff = DiffResult(snapshot_before_id="s1", snapshot_after_id="s2", changes=changes)
        detector = AnomalyDetector()
        anomalies = detector.analyze([diff], [])
        mystery = [a for a in anomalies if "unexpected" in a.description.lower()]
        assert len(mystery) > 0
        assert mystery[0].severity == DriftSeverity.HIGH

    def test_resource_disappeared(self):
        changes = (
            ResourceChange(
                resource_id="aws/ec2_instance/web-01",
                change_type=ChangeType.REMOVED,
            ),
        )
        diff = DiffResult(snapshot_before_id="s1", snapshot_after_id="s2", changes=changes)
        detector = AnomalyDetector()
        anomalies = detector.analyze([diff], [])
        disappeared = [a for a in anomalies if "disappeared" in a.description.lower()]
        assert len(disappeared) == 1
        assert disappeared[0].severity == DriftSeverity.HIGH

    def test_churn_detection(self):
        resource_id = "aws/ec2_instance/flaky-server"
        diffs = []
        for i in range(4):
            diffs.append(
                DiffResult(
                    snapshot_before_id=f"s{i}",
                    snapshot_after_id=f"s{i+1}",
                    changes=(
                        ResourceChange(
                            resource_id=resource_id,
                            change_type=ChangeType.MODIFIED,
                            field_path="state",
                        ),
                    ),
                )
            )
        detector = AnomalyDetector()
        anomalies = detector.analyze(diffs, [])
        churn = [a for a in anomalies if "churning" in a.description.lower()]
        assert len(churn) == 1
        assert "4 times" in churn[0].description

    def test_no_anomalies_for_no_changes(self, sample_snapshot):
        diff = DiffResult(
            snapshot_before_id=sample_snapshot.id,
            snapshot_after_id=sample_snapshot.id,
            changes=(),
        )
        detector = AnomalyDetector()
        anomalies = detector.analyze([diff], [sample_snapshot])
        assert len(anomalies) == 0

    def test_new_resource_medium_severity(self):
        changes = (
            ResourceChange(
                resource_id="aws/ec2_instance/planned-server",
                change_type=ChangeType.ADDED,
            ),
        )
        diff = DiffResult(snapshot_before_id="s1", snapshot_after_id="s2", changes=changes)
        detector = AnomalyDetector()
        anomalies = detector.analyze([diff], [])
        new_res = [a for a in anomalies if "new resource" in a.description.lower()]
        assert len(new_res) == 1
        assert new_res[0].severity == DriftSeverity.MEDIUM
