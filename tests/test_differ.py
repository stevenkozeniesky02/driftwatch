"""Tests for the state diffing engine."""

from driftwatch.engine.differ import StateDiffer, _diff_dicts
from driftwatch.models import ChangeType, Resource, Snapshot


class TestStateDiffer:
    def test_no_changes(self, sample_snapshot: Snapshot):
        differ = StateDiffer()
        result = differ.diff(sample_snapshot, sample_snapshot)
        assert len(result.changes) == 0

    def test_detect_added_resources(self, sample_snapshot: Snapshot, drifted_snapshot: Snapshot):
        differ = StateDiffer()
        result = differ.diff(sample_snapshot, drifted_snapshot)
        added_ids = {c.resource_id for c in result.added}
        assert "aws/ec2_instance/mystery-instance-1" in added_ids

    def test_detect_removed_resources(self, sample_snapshot: Snapshot, drifted_snapshot: Snapshot):
        differ = StateDiffer()
        result = differ.diff(sample_snapshot, drifted_snapshot)
        removed_ids = {c.resource_id for c in result.removed}
        assert "docker/container/nginx-prod" in removed_ids

    def test_detect_modified_resources(self, sample_snapshot: Snapshot, drifted_snapshot: Snapshot):
        differ = StateDiffer()
        result = differ.diff(sample_snapshot, drifted_snapshot)
        modified = result.modified
        modified_ids = {c.resource_id for c in modified}
        assert "aws/ec2_instance/web-01" in modified_ids
        assert "aws/security_group/sg-web" in modified_ids

    def test_modified_includes_field_details(self, sample_snapshot: Snapshot, drifted_snapshot: Snapshot):
        differ = StateDiffer()
        result = differ.diff(sample_snapshot, drifted_snapshot)
        instance_changes = [
            c for c in result.modified if c.resource_id == "aws/ec2_instance/web-01"
        ]
        assert len(instance_changes) > 0
        type_change = [c for c in instance_changes if c.field_path and "instance_type" in c.field_path]
        assert len(type_change) == 1
        assert type_change[0].old_value == "t3.micro"
        assert type_change[0].new_value == "m5.large"

    def test_diff_result_ids(self, sample_snapshot: Snapshot, drifted_snapshot: Snapshot):
        differ = StateDiffer()
        result = differ.diff(sample_snapshot, drifted_snapshot)
        assert result.snapshot_before_id == sample_snapshot.id
        assert result.snapshot_after_id == drifted_snapshot.id

    def test_empty_snapshots(self):
        differ = StateDiffer()
        s1 = Snapshot.create([])
        s2 = Snapshot.create([])
        result = differ.diff(s1, s2)
        assert len(result.changes) == 0

    def test_all_added(self, sample_resources: list[Resource]):
        differ = StateDiffer()
        s1 = Snapshot.create([])
        s2 = Snapshot.create(sample_resources)
        result = differ.diff(s1, s2)
        assert len(result.added) == len(sample_resources)
        assert len(result.removed) == 0

    def test_all_removed(self, sample_resources: list[Resource]):
        differ = StateDiffer()
        s1 = Snapshot.create(sample_resources)
        s2 = Snapshot.create([])
        result = differ.diff(s1, s2)
        assert len(result.removed) == len(sample_resources)
        assert len(result.added) == 0


class TestDiffDicts:
    def test_no_changes(self):
        assert _diff_dicts({"a": 1}, {"a": 1}) == []

    def test_value_changed(self):
        result = _diff_dicts({"a": 1}, {"a": 2})
        assert len(result) == 1
        assert result[0] == ("a", 1, 2, "changed")

    def test_key_added(self):
        result = _diff_dicts({}, {"a": 1})
        assert len(result) == 1
        assert result[0][3] == "added"

    def test_key_removed(self):
        result = _diff_dicts({"a": 1}, {})
        assert len(result) == 1
        assert result[0][3] == "removed"

    def test_nested_diff(self):
        result = _diff_dicts({"a": {"b": 1}}, {"a": {"b": 2}})
        assert len(result) == 1
        assert result[0] == ("a.b", 1, 2, "changed")
