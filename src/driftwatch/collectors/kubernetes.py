"""Kubernetes resource collector."""

from __future__ import annotations

import json

from driftwatch.collectors.base import BaseCollector, _has_command
from driftwatch.models import CollectorType, Resource


class KubernetesCollector(BaseCollector):
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.KUBERNETES

    def is_available(self) -> bool:
        return _has_command("kubectl")

    def collect(self) -> list[Resource]:
        resources: list[Resource] = []
        resources.extend(self._collect_pods())
        resources.extend(self._collect_services())
        resources.extend(self._collect_deployments())
        return resources

    def _collect_pods(self) -> list[Resource]:
        output = self._run_command(
            ["kubectl", "get", "pods", "--all-namespaces", "-o", "json"]
        )
        if not output:
            return []
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        resources = []
        for pod in data.get("items", []):
            meta = pod.get("metadata", {})
            status = pod.get("status", {})
            ns = meta.get("namespace", "default")
            resources.append(
                Resource(
                    type="pod",
                    name=f"{ns}/{meta.get('name', 'unknown')}",
                    provider="kubernetes",
                    properties={
                        "namespace": ns,
                        "phase": status.get("phase", ""),
                        "node": status.get("hostIP", ""),
                        "containers": len(pod.get("spec", {}).get("containers", [])),
                        "labels": meta.get("labels", {}),
                    },
                )
            )
        return resources

    def _collect_services(self) -> list[Resource]:
        output = self._run_command(
            ["kubectl", "get", "services", "--all-namespaces", "-o", "json"]
        )
        if not output:
            return []
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        return [
            Resource(
                type="service",
                name=f"{svc['metadata'].get('namespace', 'default')}/{svc['metadata']['name']}",
                provider="kubernetes",
                properties={
                    "type": svc.get("spec", {}).get("type", ""),
                    "cluster_ip": svc.get("spec", {}).get("clusterIP", ""),
                    "ports": [
                        {"port": p.get("port"), "protocol": p.get("protocol")}
                        for p in svc.get("spec", {}).get("ports", [])
                    ],
                },
            )
            for svc in data.get("items", [])
        ]

    def _collect_deployments(self) -> list[Resource]:
        output = self._run_command(
            ["kubectl", "get", "deployments", "--all-namespaces", "-o", "json"]
        )
        if not output:
            return []
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        return [
            Resource(
                type="deployment",
                name=f"{d['metadata'].get('namespace', 'default')}/{d['metadata']['name']}",
                provider="kubernetes",
                properties={
                    "replicas": d.get("spec", {}).get("replicas", 0),
                    "available": d.get("status", {}).get("availableReplicas", 0),
                    "strategy": d.get("spec", {}).get("strategy", {}).get("type", ""),
                },
            )
            for d in data.get("items", [])
        ]
