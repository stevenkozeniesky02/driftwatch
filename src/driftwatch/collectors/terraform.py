"""Terraform state collector."""

from __future__ import annotations

import json

from driftwatch.collectors.base import BaseCollector, _has_command
from driftwatch.models import CollectorType, Resource


class TerraformCollector(BaseCollector):
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.TERRAFORM

    def is_available(self) -> bool:
        return _has_command("terraform")

    def collect(self) -> list[Resource]:
        output = self._run_command(["terraform", "show", "-json"])
        if not output:
            return []
        try:
            state = json.loads(output)
        except json.JSONDecodeError:
            return []
        return self._parse_state(state)

    def _parse_state(self, state: dict) -> list[Resource]:
        resources: list[Resource] = []
        root_module = state.get("values", {}).get("root_module", {})
        resources.extend(self._extract_resources(root_module))
        for child in root_module.get("child_modules", []):
            resources.extend(self._extract_resources(child))
        return resources

    def _extract_resources(self, module: dict) -> list[Resource]:
        resources = []
        for r in module.get("resources", []):
            deps = tuple(r.get("depends_on", []))
            resources.append(
                Resource(
                    type=r.get("type", "unknown"),
                    name=r.get("name", "unknown"),
                    provider=r.get("provider_name", "terraform"),
                    properties=r.get("values", {}),
                    dependencies=deps,
                )
            )
        return resources


def parse_terraform_plan(plan_json: dict) -> list[dict]:
    """Parse a terraform plan JSON to extract planned changes."""
    changes = []
    for rc in plan_json.get("resource_changes", []):
        actions = rc.get("change", {}).get("actions", [])
        before = rc.get("change", {}).get("before") or {}
        after = rc.get("change", {}).get("after") or {}
        changes.append({
            "address": rc.get("address", ""),
            "type": rc.get("type", ""),
            "name": rc.get("name", ""),
            "actions": actions,
            "before": before,
            "after": after,
            "provider": rc.get("provider_name", ""),
        })
    return changes
