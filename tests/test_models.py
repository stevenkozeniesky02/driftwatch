"""Tests for domain models."""

from driftwatch.models import (
    ChangeType,
    DiffResult,
    DriftSeverity,
    Resource,
    ResourceChange,
    Snapshot,
)


class TestResource:
    def test_id_format(self):
        r = Resource(type="ec2_instance", name="web-01", provider="aws")
        assert r.id == "aws/ec2_instance/web-01"

    def test_frozen(self):
        r = Resource(type="ec2_instance", name="web-01", provider="aws")
        try:
            r.name = "changed"  # type: ignore
            assert False, "Should not be mutable"
        except AttributeError:
            pass

    def test_properties_default(self):
        r = Resource(type="pod", name="test", provider="kubernetes")
        assert r.properties == {}
        assert r.dependencies == ()


class TestSnapshot:
    def test_create_generates_id(self):
        resources = [Resource(type="t", name="n", provider="p")]
        snap = Snapshot.create(resources)
        assert len(snap.id) == 12
        assert snap.timestamp is not None
        assert len(snap.resources) == 1

    def test_create_with_metadata(self):
        snap = Snapshot.create([], metadata={"demo": True})
        assert snap.metadata["demo"] is True

    def test_frozen(self):
        snap = Snapshot.create([])
        try:
            snap.id = "changed"  # type: ignore
            assert False, "Should not be mutable"
        except AttributeError:
            pass


class TestDiffResult:
    def test_change_type_filters(self):
        changes = (
            ResourceChange(resource_id="a", change_type=ChangeType.ADDED),
            ResourceChange(resource_id="b", change_type=ChangeType.REMOVED),
            ResourceChange(resource_id="c", change_type=ChangeType.MODIFIED, field_path="x"),
            ResourceChange(resource_id="d", change_type=ChangeType.MODIFIED, field_path="y"),
        )
        diff = DiffResult(
            snapshot_before_id="s1",
            snapshot_after_id="s2",
            changes=changes,
        )
        assert len(diff.added) == 1
        assert len(diff.removed) == 1
        assert len(diff.modified) == 2


class TestEnums:
    def test_severity_values(self):
        assert DriftSeverity.LOW.value == "low"
        assert DriftSeverity.CRITICAL.value == "critical"

    def test_change_type_values(self):
        assert ChangeType.ADDED.value == "added"
        assert ChangeType.REMOVED.value == "removed"
        assert ChangeType.MODIFIED.value == "modified"
