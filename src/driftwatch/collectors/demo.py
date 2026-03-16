"""Demo collector that generates realistic fake infrastructure snapshots."""

from __future__ import annotations

import random

from driftwatch.collectors.base import BaseCollector
from driftwatch.models import CollectorType, Resource

_INSTANCE_TYPES = ["t3.micro", "t3.small", "t3.medium", "m5.large", "m5.xlarge", "c5.2xlarge"]
_REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]
_IMAGES = [
    "nginx:1.25", "redis:7.2", "postgres:16", "node:20-slim",
    "python:3.12-slim", "grafana/grafana:10.2", "prom/prometheus:v2.48",
]
_SG_DESCRIPTIONS = [
    "Allow HTTPS from anywhere", "Internal API access", "Database access",
    "Monitoring stack", "Load balancer SG", "SSH bastion access",
]
_SERVICE_NAMES = ["api-gateway", "auth-service", "user-service", "payment-service", "notification"]
_BUCKET_NAMES = ["logs-prod", "backups-daily", "static-assets", "ml-models", "config-store"]

# Mutable state tracker for generating realistic drift across calls
_call_count = 0


class DemoCollector(BaseCollector):
    """Generates fake infrastructure that mutates realistically between calls."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.DEMO

    def is_available(self) -> bool:
        return True

    def collect(self) -> list[Resource]:
        global _call_count
        _call_count += 1
        resources: list[Resource] = []
        resources.extend(self._generate_ec2_instances())
        resources.extend(self._generate_security_groups())
        resources.extend(self._generate_containers())
        resources.extend(self._generate_s3_buckets())
        resources.extend(self._generate_k8s_services())
        resources = self._apply_drift(resources)
        return resources

    def _generate_ec2_instances(self) -> list[Resource]:
        instances = []
        for i in range(self._rng.randint(3, 6)):
            instances.append(
                Resource(
                    type="ec2_instance",
                    name=f"web-server-{i+1:02d}",
                    provider="aws",
                    properties={
                        "instance_id": f"i-{self._rng.randbytes(8).hex()[:17]}",
                        "instance_type": self._rng.choice(_INSTANCE_TYPES[:3]),
                        "state": "running",
                        "region": self._rng.choice(_REGIONS),
                        "vpc_id": "vpc-0abc123def456",
                        "security_groups": ["sg-web-01", "sg-internal-01"],
                    },
                    dependencies=("aws/vpc/vpc-0abc123def456",),
                )
            )
        return instances

    def _generate_security_groups(self) -> list[Resource]:
        groups = []
        for i, desc in enumerate(_SG_DESCRIPTIONS):
            ingress_count = self._rng.randint(1, 5)
            groups.append(
                Resource(
                    type="security_group",
                    name=f"sg-{desc.lower().replace(' ', '-')[:20]}-{i:02d}",
                    provider="aws",
                    properties={
                        "group_id": f"sg-{self._rng.randbytes(6).hex()[:12]}",
                        "vpc_id": "vpc-0abc123def456",
                        "description": desc,
                        "ingress_rules": ingress_count,
                        "egress_rules": self._rng.randint(1, 3),
                    },
                    dependencies=("aws/vpc/vpc-0abc123def456",),
                )
            )
        return groups

    def _generate_containers(self) -> list[Resource]:
        containers = []
        for img in self._rng.sample(_IMAGES, k=min(5, len(_IMAGES))):
            name = img.split("/")[-1].split(":")[0]
            containers.append(
                Resource(
                    type="container",
                    name=f"{name}-prod",
                    provider="docker",
                    properties={
                        "image": img,
                        "status": "Up 3 days",
                        "ports": f"{self._rng.randint(3000,9999)}->80/tcp",
                        "state": "running",
                    },
                )
            )
        return containers

    def _generate_s3_buckets(self) -> list[Resource]:
        return [
            Resource(
                type="s3_bucket",
                name=f"acme-{name}",
                provider="aws",
                properties={
                    "region": self._rng.choice(_REGIONS),
                    "versioning": name in ("logs-prod", "backups-daily"),
                    "encryption": True,
                },
            )
            for name in _BUCKET_NAMES
        ]

    def _generate_k8s_services(self) -> list[Resource]:
        services = []
        for svc_name in _SERVICE_NAMES:
            replicas = self._rng.randint(2, 5)
            services.append(
                Resource(
                    type="deployment",
                    name=f"prod/{svc_name}",
                    provider="kubernetes",
                    properties={
                        "replicas": replicas,
                        "available": replicas,
                        "strategy": "RollingUpdate",
                        "image": f"acme/{svc_name}:v1.{self._rng.randint(0,9)}.{self._rng.randint(0,20)}",
                    },
                )
            )
        return services

    def _apply_drift(self, resources: list[Resource]) -> list[Resource]:
        """Simulate realistic drift by mutating some resources."""
        if _call_count <= 1:
            return resources

        drifted: list[Resource] = []
        for r in resources:
            if self._rng.random() < 0.15:
                r = self._mutate_resource(r)
            drifted.append(r)

        # Occasionally add a surprise resource
        if self._rng.random() < 0.3:
            drifted.append(
                Resource(
                    type="ec2_instance",
                    name=f"mystery-instance-{_call_count}",
                    provider="aws",
                    properties={
                        "instance_id": f"i-mystery{_call_count:04d}",
                        "instance_type": "m5.xlarge",
                        "state": "running",
                        "region": "us-east-1",
                        "security_groups": ["sg-unknown-01"],
                    },
                )
            )

        # Occasionally remove a resource
        if self._rng.random() < 0.2 and len(drifted) > 5:
            idx = self._rng.randint(0, len(drifted) - 1)
            drifted = drifted[:idx] + drifted[idx + 1 :]

        return drifted

    def _mutate_resource(self, resource: Resource) -> Resource:
        """Create a new Resource with drifted properties."""
        new_props = dict(resource.properties)

        if resource.type == "security_group":
            new_props["ingress_rules"] = new_props.get("ingress_rules", 1) + self._rng.randint(1, 3)
        elif resource.type == "ec2_instance":
            new_props["instance_type"] = self._rng.choice(_INSTANCE_TYPES)
        elif resource.type == "deployment":
            current = new_props.get("replicas", 2)
            new_props["replicas"] = max(1, current + self._rng.choice([-1, 1, 2]))
            new_props["available"] = new_props["replicas"]
        elif resource.type == "container":
            img_base = new_props.get("image", "nginx:1.25").split(":")[0]
            new_props["image"] = f"{img_base}:{self._rng.randint(1,9)}.{self._rng.randint(0,50)}"

        return Resource(
            type=resource.type,
            name=resource.name,
            provider=resource.provider,
            properties=new_props,
            dependencies=resource.dependencies,
        )
