"""Docker container collector."""

from __future__ import annotations

import json

from driftwatch.collectors.base import BaseCollector, _has_command
from driftwatch.models import CollectorType, Resource


class DockerCollector(BaseCollector):
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.DOCKER

    def is_available(self) -> bool:
        return _has_command("docker")

    def collect(self) -> list[Resource]:
        resources: list[Resource] = []
        resources.extend(self._collect_containers())
        resources.extend(self._collect_images())
        resources.extend(self._collect_networks())
        return resources

    def _collect_containers(self) -> list[Resource]:
        output = self._run_command(
            ["docker", "ps", "-a", "--format", "{{json .}}"]
        )
        if not output:
            return []
        resources = []
        for line in output.strip().splitlines():
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            resources.append(
                Resource(
                    type="container",
                    name=c.get("Names", c.get("ID", "unknown")),
                    provider="docker",
                    properties={
                        "id": c.get("ID", ""),
                        "image": c.get("Image", ""),
                        "status": c.get("Status", ""),
                        "ports": c.get("Ports", ""),
                        "state": c.get("State", ""),
                    },
                )
            )
        return resources

    def _collect_images(self) -> list[Resource]:
        output = self._run_command(
            ["docker", "images", "--format", "{{json .}}"]
        )
        if not output:
            return []
        resources = []
        for line in output.strip().splitlines():
            try:
                img = json.loads(line)
            except json.JSONDecodeError:
                continue
            repo = img.get("Repository", "none")
            tag = img.get("Tag", "latest")
            resources.append(
                Resource(
                    type="image",
                    name=f"{repo}:{tag}",
                    provider="docker",
                    properties={
                        "id": img.get("ID", ""),
                        "size": img.get("Size", ""),
                        "created": img.get("CreatedSince", ""),
                    },
                )
            )
        return resources

    def _collect_networks(self) -> list[Resource]:
        output = self._run_command(
            ["docker", "network", "ls", "--format", "{{json .}}"]
        )
        if not output:
            return []
        resources = []
        for line in output.strip().splitlines():
            try:
                net = json.loads(line)
            except json.JSONDecodeError:
                continue
            resources.append(
                Resource(
                    type="network",
                    name=net.get("Name", "unknown"),
                    provider="docker",
                    properties={
                        "id": net.get("ID", ""),
                        "driver": net.get("Driver", ""),
                        "scope": net.get("Scope", ""),
                    },
                )
            )
        return resources
