"""Tests for the FastAPI web dashboard API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from driftwatch.db import Database
from driftwatch.models import Resource, Snapshot
from driftwatch.web.app import create_app


@pytest.fixture
def client(tmp_path: Path, sample_resources: list[Resource], drifted_resources: list[Resource]):
    db = Database(tmp_path / "api_test.db")
    snap1 = Snapshot.create(sample_resources, metadata={"demo": True})
    db.save_snapshot(snap1)
    snap2 = Snapshot.create(drifted_resources, metadata={"demo": True})
    db.save_snapshot(snap2)

    app = create_app(db)
    with TestClient(app) as c:
        yield c, snap1, snap2
    db.close()


class TestSnapshotsAPI:
    def test_list_snapshots(self, client):
        c, snap1, snap2 = client
        resp = c.get("/api/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["snapshots"]) == 2
        assert data["total"] == 2

    def test_list_snapshots_with_limit(self, client):
        c, _, _ = client
        resp = c.get("/api/snapshots?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["snapshots"]) == 1

    def test_get_snapshot(self, client):
        c, snap1, _ = client
        resp = c.get(f"/api/snapshots/{snap1.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == snap1.id
        assert len(data["resources"]) == len(snap1.resources)

    def test_get_snapshot_not_found(self, client):
        c, _, _ = client
        resp = c.get("/api/snapshots/nonexistent")
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestDiffAPI:
    def test_diff_two_snapshots(self, client):
        c, snap1, snap2 = client
        resp = c.get(f"/api/diff/{snap1.id}/{snap2.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "changes" in data
        assert "summary" in data
        assert data["summary"]["total"] > 0

    def test_diff_not_found(self, client):
        c, snap1, _ = client
        resp = c.get(f"/api/diff/{snap1.id}/nonexistent")
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestAnomaliesAPI:
    def test_get_anomalies(self, client):
        c, _, _ = client
        resp = c.get("/api/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data

    def test_anomalies_empty_db(self, tmp_path: Path):
        db = Database(tmp_path / "empty.db")
        app = create_app(db)
        with TestClient(app) as c:
            resp = c.get("/api/anomalies")
            assert resp.status_code == 200
            assert resp.json()["anomalies"] == []
        db.close()


class TestGraphAPI:
    def test_resource_graph(self, client):
        c, snap1, _ = client
        resp = c.get(f"/api/graph/{snap1.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0

    def test_graph_has_edges(self, client):
        c, snap1, _ = client
        resp = c.get(f"/api/graph/{snap1.id}")
        data = resp.json()
        # Resources with dependencies should have edges
        assert len(data["edges"]) > 0


class TestHistoryAPI:
    def test_diff_history(self, client):
        c, _, _ = client
        resp = c.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "diffs" in data


class TestStaticFiles:
    def test_serves_index(self, client):
        c, _, _ = client
        resp = c.get("/")
        assert resp.status_code == 200
        assert "DriftWatch" in resp.text
