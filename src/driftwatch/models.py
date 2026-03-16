"""Domain models for DriftWatch."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DriftSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class CollectorType(str, Enum):
    AWS = "aws"
    TERRAFORM = "terraform"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    DEMO = "demo"


@dataclass(frozen=True)
class Resource:
    type: str
    name: str
    provider: str
    properties: dict[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    @property
    def id(self) -> str:
        return f"{self.provider}/{self.type}/{self.name}"


@dataclass(frozen=True)
class Snapshot:
    id: str
    timestamp: datetime
    resources: tuple[Resource, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def create(resources: list[Resource], metadata: dict[str, Any] | None = None) -> Snapshot:
        now = datetime.now(timezone.utc)
        raw = json.dumps(
            {"ts": now.isoformat(), "count": len(resources)},
            sort_keys=True,
        )
        snap_id = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return Snapshot(
            id=snap_id,
            timestamp=now,
            resources=tuple(resources),
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class ResourceChange:
    resource_id: str
    change_type: ChangeType
    field_path: str | None = None
    old_value: Any = None
    new_value: Any = None


@dataclass(frozen=True)
class DiffResult:
    snapshot_before_id: str
    snapshot_after_id: str
    changes: tuple[ResourceChange, ...]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def added(self) -> tuple[ResourceChange, ...]:
        return tuple(c for c in self.changes if c.change_type == ChangeType.ADDED)

    @property
    def removed(self) -> tuple[ResourceChange, ...]:
        return tuple(c for c in self.changes if c.change_type == ChangeType.REMOVED)

    @property
    def modified(self) -> tuple[ResourceChange, ...]:
        return tuple(c for c in self.changes if c.change_type == ChangeType.MODIFIED)


@dataclass(frozen=True)
class Anomaly:
    resource_id: str
    description: str
    severity: DriftSeverity
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PredictionResult:
    affected_resources: tuple[str, ...]
    risk_level: DriftSeverity
    description: str
    details: dict[str, Any] = field(default_factory=dict)
