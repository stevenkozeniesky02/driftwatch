"""Tests for the SQLite database layer."""

from pathlib import Path

from driftwatch.db import Database
from driftwatch.models import (
    ChangeType,
    DiffResult,
    Resource,
    ResourceChange,
    Snapshot,
)


class TestDatabase:
    def test_save_and_get_snapshot(self, tmp_db: Database, sample_snapshot: Snapshot):
        tmp_db.save_snapshot(sample_snapshot)
        retrieved = tmp_db.get_snapshot(sample_snapshot.id)
        assert retrieved is not None
        assert retrieved.id == sample_snapshot.id
        assert len(retrieved.resources) == len(sample_snapshot.resources)

    def test_get_nonexistent_snapshot(self, tmp_db: Database):
        assert tmp_db.get_snapshot("nonexistent") is None

    def test_list_snapshots_ordered(self, tmp_db: Database, sample_resources: list[Resource]):
        import time

        snap1 = Snapshot.create(sample_resources[:2])
        tmp_db.save_snapshot(snap1)
        time.sleep(0.01)
        snap2 = Snapshot.create(sample_resources[2:])
        tmp_db.save_snapshot(snap2)

        snapshots = tmp_db.list_snapshots()
        assert len(snapshots) == 2
        # Most recent first
        assert snapshots[0].timestamp >= snapshots[1].timestamp

    def test_get_latest_snapshots(self, tmp_db: Database, sample_resources: list[Resource]):
        for i in range(5):
            tmp_db.save_snapshot(Snapshot.create(sample_resources[:i + 1]))

        latest = tmp_db.get_latest_snapshots(2)
        assert len(latest) == 2

    def test_snapshot_count(self, tmp_db: Database, sample_resources: list[Resource]):
        assert tmp_db.snapshot_count() == 0
        tmp_db.save_snapshot(Snapshot.create(sample_resources))
        assert tmp_db.snapshot_count() == 1

    def test_save_and_get_diff(self, tmp_db: Database):
        changes = (
            ResourceChange(resource_id="test/r/1", change_type=ChangeType.ADDED),
            ResourceChange(
                resource_id="test/r/2",
                change_type=ChangeType.MODIFIED,
                field_path="prop",
                old_value="old",
                new_value="new",
            ),
        )
        diff = DiffResult(
            snapshot_before_id="s1",
            snapshot_after_id="s2",
            changes=changes,
        )
        tmp_db.save_diff(diff)
        diffs = tmp_db.get_diffs()
        assert len(diffs) == 1
        assert diffs[0]["before_id"] == "s1"
        assert len(diffs[0]["changes"]) == 2

    def test_resource_properties_roundtrip(self, tmp_db: Database):
        resource = Resource(
            type="ec2",
            name="test",
            provider="aws",
            properties={"nested": {"key": [1, 2, 3]}, "flag": True},
            dependencies=("aws/vpc/vpc-1",),
        )
        snap = Snapshot.create([resource])
        tmp_db.save_snapshot(snap)
        retrieved = tmp_db.get_snapshot(snap.id)
        assert retrieved is not None
        r = retrieved.resources[0]
        assert r.properties["nested"]["key"] == [1, 2, 3]
        assert r.properties["flag"] is True
        assert r.dependencies == ("aws/vpc/vpc-1",)

    def test_close_and_reopen(self, tmp_path: Path, sample_resources: list[Resource]):
        db_path = tmp_path / "reopen.db"
        db = Database(db_path)
        snap = Snapshot.create(sample_resources)
        db.save_snapshot(snap)
        db.close()

        db2 = Database(db_path)
        retrieved = db2.get_snapshot(snap.id)
        assert retrieved is not None
        assert len(retrieved.resources) == len(sample_resources)
        db2.close()
