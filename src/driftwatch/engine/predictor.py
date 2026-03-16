"""Predict consequences of Terraform plan changes on existing infrastructure."""

from __future__ import annotations

import json
from pathlib import Path

from driftwatch.collectors.terraform import parse_terraform_plan
from driftwatch.models import DriftSeverity, PredictionResult, Snapshot

_DESTRUCTIVE_ACTIONS = {"delete", "replace"}
_SENSITIVE_TYPES = {
    "aws_security_group", "aws_iam_role", "aws_iam_policy",
    "aws_db_instance", "aws_rds_cluster", "aws_elasticache_cluster",
    "aws_s3_bucket", "aws_kms_key", "aws_vpc", "aws_subnet",
}


class PlanPredictor:
    """Analyzes a Terraform plan against current state to predict impact."""

    def predict(
        self, plan_path: str | Path, current_snapshot: Snapshot | None = None
    ) -> list[PredictionResult]:
        plan_data = self._load_plan(plan_path)
        changes = parse_terraform_plan(plan_data)

        if not changes:
            return [
                PredictionResult(
                    affected_resources=(),
                    risk_level=DriftSeverity.LOW,
                    description="No resource changes detected in plan.",
                )
            ]

        results: list[PredictionResult] = []
        results.extend(self._analyze_destructive_changes(changes))
        results.extend(self._analyze_security_impact(changes))
        results.extend(self._analyze_dependency_impact(changes, current_snapshot))
        results.append(self._generate_summary(changes))
        return results

    def _load_plan(self, plan_path: str | Path) -> dict:
        path = Path(plan_path)
        if not path.exists():
            raise FileNotFoundError(f"Plan file not found: {path}")
        content = path.read_text()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in plan file: {e}") from e

    def _analyze_destructive_changes(self, changes: list[dict]) -> list[PredictionResult]:
        results = []
        for change in changes:
            actions = set(change.get("actions", []))
            if actions & _DESTRUCTIVE_ACTIONS:
                results.append(
                    PredictionResult(
                        affected_resources=(change["address"],),
                        risk_level=DriftSeverity.CRITICAL,
                        description=(
                            f"Destructive action ({', '.join(actions & _DESTRUCTIVE_ACTIONS)}) "
                            f"on {change['address']}"
                        ),
                        details={
                            "type": change["type"],
                            "actions": change["actions"],
                        },
                    )
                )
        return results

    def _analyze_security_impact(self, changes: list[dict]) -> list[PredictionResult]:
        results = []
        for change in changes:
            if change.get("type", "") in _SENSITIVE_TYPES:
                results.append(
                    PredictionResult(
                        affected_resources=(change["address"],),
                        risk_level=DriftSeverity.HIGH,
                        description=f"Security-sensitive resource change: {change['address']}",
                        details={
                            "type": change["type"],
                            "actions": change["actions"],
                        },
                    )
                )
        return results

    def _analyze_dependency_impact(
        self, changes: list[dict], snapshot: Snapshot | None
    ) -> list[PredictionResult]:
        if not snapshot:
            return []
        changed_ids = {c["address"] for c in changes}
        dep_map: dict[str, list[str]] = {}
        for r in snapshot.resources:
            for dep in r.dependencies:
                dep_map.setdefault(dep, []).append(r.id)

        results = []
        for cid in changed_ids:
            dependents = dep_map.get(cid, [])
            if dependents:
                results.append(
                    PredictionResult(
                        affected_resources=tuple(dependents),
                        risk_level=DriftSeverity.MEDIUM,
                        description=(
                            f"Change to {cid} may affect {len(dependents)} dependent resource(s)"
                        ),
                        details={"dependents": dependents},
                    )
                )
        return results

    def _generate_summary(self, changes: list[dict]) -> PredictionResult:
        action_counts: dict[str, int] = {}
        for change in changes:
            for action in change.get("actions", []):
                action_counts[action] = action_counts.get(action, 0) + 1

        has_destructive = bool(set(action_counts) & _DESTRUCTIVE_ACTIONS)
        risk = DriftSeverity.HIGH if has_destructive else DriftSeverity.MEDIUM

        summary_parts = [f"{count} {action}" for action, count in sorted(action_counts.items())]
        return PredictionResult(
            affected_resources=tuple(c["address"] for c in changes),
            risk_level=risk,
            description=f"Plan summary: {', '.join(summary_parts)} across {len(changes)} resources",
            details={"action_counts": action_counts},
        )
