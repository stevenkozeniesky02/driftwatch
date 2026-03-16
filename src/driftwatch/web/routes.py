"""API routes for the DriftWatch web dashboard."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from driftwatch.db import Database
from driftwatch.engine.anomaly import AnomalyDetector
from driftwatch.engine.differ import StateDiffer


def _get_db(request: Request) -> Database:
    return request.app.state.db


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/snapshots")
    def list_snapshots(request: Request, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        db = _get_db(request)
        snapshots = db.list_snapshots(limit=limit, offset=offset)
        return {
            "snapshots": [
                {
                    "id": s.id,
                    "timestamp": s.timestamp.isoformat(),
                    "resource_count": len(s.resources),
                    "providers": sorted({r.provider for r in s.resources}),
                    "metadata": s.metadata,
                }
                for s in snapshots
            ],
            "total": db.snapshot_count(),
        }

    @router.get("/snapshots/{snapshot_id}")
    def get_snapshot(request: Request, snapshot_id: str) -> dict[str, Any]:
        db = _get_db(request)
        snapshot = db.get_snapshot(snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return {
            "id": snapshot.id,
            "timestamp": snapshot.timestamp.isoformat(),
            "resources": [
                {
                    "id": r.id,
                    "type": r.type,
                    "name": r.name,
                    "provider": r.provider,
                    "properties": r.properties,
                    "dependencies": list(r.dependencies),
                }
                for r in snapshot.resources
            ],
            "metadata": snapshot.metadata,
        }

    @router.get("/diff/{before_id}/{after_id}")
    def diff_snapshots(
        request: Request, before_id: str, after_id: str
    ) -> dict[str, Any]:
        db = _get_db(request)
        before = db.get_snapshot(before_id)
        after = db.get_snapshot(after_id)
        if not before or not after:
            raise HTTPException(status_code=404, detail="One or both snapshots not found")

        differ = StateDiffer()
        result = differ.diff(before, after)

        return {
            "before_id": result.snapshot_before_id,
            "after_id": result.snapshot_after_id,
            "changes": [
                {
                    "resource_id": c.resource_id,
                    "change_type": c.change_type.value,
                    "field_path": c.field_path,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                }
                for c in result.changes
            ],
            "summary": {
                "added": len(result.added),
                "removed": len(result.removed),
                "modified": len(result.modified),
                "total": len(result.changes),
            },
        }

    @router.get("/anomalies")
    def get_anomalies(request: Request, limit: int = 10) -> dict[str, Any]:
        db = _get_db(request)
        snapshots = db.get_latest_snapshots(limit)
        if len(snapshots) < 2:
            return {"anomalies": [], "message": "Need at least 2 snapshots"}

        differ = StateDiffer()
        diffs = []
        for i in range(len(snapshots) - 1):
            diffs.append(differ.diff(snapshots[i + 1], snapshots[i]))

        detector = AnomalyDetector()
        anomalies = detector.analyze(diffs, snapshots)

        return {
            "anomalies": [
                {
                    "resource_id": a.resource_id,
                    "description": a.description,
                    "severity": a.severity.value,
                    "detected_at": a.detected_at.isoformat(),
                }
                for a in anomalies
            ]
        }

    @router.get("/graph/{snapshot_id}")
    def resource_graph(request: Request, snapshot_id: str) -> dict[str, Any]:
        db = _get_db(request)
        snapshot = db.get_snapshot(snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        nodes = []
        edges = []
        for r in snapshot.resources:
            nodes.append({
                "id": r.id,
                "type": r.type,
                "name": r.name,
                "provider": r.provider,
            })
            for dep in r.dependencies:
                edges.append({"source": r.id, "target": dep})

        return {"nodes": nodes, "edges": edges}

    @router.get("/history")
    def diff_history(request: Request, limit: int = 50) -> dict[str, Any]:
        db = _get_db(request)
        return {"diffs": db.get_diffs(limit=limit)}

    return router
