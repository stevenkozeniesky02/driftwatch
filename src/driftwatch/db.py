"""SQLite backend for storing snapshots as JSON with timestamps."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from driftwatch.models import DiffResult, Resource, Snapshot

DEFAULT_DB_PATH = Path.home() / ".driftwatch" / "driftwatch.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    resources_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS diffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    before_id TEXT NOT NULL,
    after_id TEXT NOT NULL,
    changes_json TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (before_id) REFERENCES snapshots(id),
    FOREIGN KEY (after_id) REFERENCES snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_diffs_timestamp ON diffs(timestamp);
"""


def _serialize_resource(r: Resource) -> dict[str, Any]:
    return {
        "type": r.type,
        "name": r.name,
        "provider": r.provider,
        "properties": r.properties,
        "dependencies": list(r.dependencies),
    }


def _deserialize_resource(data: dict[str, Any]) -> Resource:
    return Resource(
        type=data["type"],
        name=data["name"],
        provider=data["provider"],
        properties=data.get("properties", {}),
        dependencies=tuple(data.get("dependencies", [])),
    )


class Database:
    """Immutable-friendly SQLite store for DriftWatch data."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def save_snapshot(self, snapshot: Snapshot) -> None:
        resources_json = json.dumps([_serialize_resource(r) for r in snapshot.resources])
        metadata_json = json.dumps(snapshot.metadata)
        self._conn.execute(
            "INSERT OR REPLACE INTO snapshots (id, timestamp, resources_json, metadata_json) "
            "VALUES (?, ?, ?, ?)",
            (snapshot.id, snapshot.timestamp.isoformat(), resources_json, metadata_json),
        )
        self._conn.commit()

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        row = self._conn.execute(
            "SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_snapshot(row)

    def list_snapshots(self, limit: int = 50, offset: int = 0) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def get_latest_snapshots(self, count: int = 2) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT ?", (count,)
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def save_diff(self, diff: DiffResult) -> None:
        changes_json = json.dumps([asdict(c) for c in diff.changes])
        self._conn.execute(
            "INSERT INTO diffs (before_id, after_id, changes_json, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (
                diff.snapshot_before_id,
                diff.snapshot_after_id,
                changes_json,
                diff.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def get_diffs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM diffs ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            {
                "before_id": r["before_id"],
                "after_id": r["after_id"],
                "changes": json.loads(r["changes_json"]),
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    def snapshot_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM snapshots").fetchone()
        return row["cnt"]

    def _row_to_snapshot(self, row: sqlite3.Row) -> Snapshot:
        resources = [_deserialize_resource(r) for r in json.loads(row["resources_json"])]
        return Snapshot(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]).replace(tzinfo=timezone.utc),
            resources=tuple(resources),
            metadata=json.loads(row["metadata_json"]),
        )
