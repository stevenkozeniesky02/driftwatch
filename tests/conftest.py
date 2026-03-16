"""Shared fixtures for DriftWatch tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from driftwatch.db import Database
from driftwatch.models import Resource, Snapshot


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """Provide a fresh temporary database."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    yield db
    db.close()


@pytest.fixture
def sample_resources() -> list[Resource]:
    return [
        Resource(
            type="ec2_instance",
            name="web-01",
            provider="aws",
            properties={"instance_type": "t3.micro", "state": "running"},
            dependencies=("aws/vpc/vpc-123",),
        ),
        Resource(
            type="ec2_instance",
            name="web-02",
            provider="aws",
            properties={"instance_type": "t3.small", "state": "running"},
            dependencies=("aws/vpc/vpc-123",),
        ),
        Resource(
            type="security_group",
            name="sg-web",
            provider="aws",
            properties={"ingress_rules": 3, "egress_rules": 1},
            dependencies=("aws/vpc/vpc-123",),
        ),
        Resource(
            type="container",
            name="nginx-prod",
            provider="docker",
            properties={"image": "nginx:1.25", "state": "running"},
        ),
        Resource(
            type="deployment",
            name="prod/api-gateway",
            provider="kubernetes",
            properties={"replicas": 3, "available": 3, "strategy": "RollingUpdate"},
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_resources: list[Resource]) -> Snapshot:
    return Snapshot.create(sample_resources, metadata={"demo": True})


@pytest.fixture
def drifted_resources(sample_resources: list[Resource]) -> list[Resource]:
    """Resources with some drift applied."""
    drifted = list(sample_resources)
    # Modify: instance type changed
    drifted[0] = Resource(
        type="ec2_instance",
        name="web-01",
        provider="aws",
        properties={"instance_type": "m5.large", "state": "running"},
        dependencies=("aws/vpc/vpc-123",),
    )
    # Modify: security group rules changed
    drifted[2] = Resource(
        type="security_group",
        name="sg-web",
        provider="aws",
        properties={"ingress_rules": 5, "egress_rules": 2},
        dependencies=("aws/vpc/vpc-123",),
    )
    # Add: new mystery instance
    drifted.append(
        Resource(
            type="ec2_instance",
            name="mystery-instance-1",
            provider="aws",
            properties={"instance_type": "m5.xlarge", "state": "running"},
        )
    )
    # Remove: docker container (remove index 3)
    drifted.pop(3)
    return drifted


@pytest.fixture
def drifted_snapshot(drifted_resources: list[Resource]) -> Snapshot:
    return Snapshot.create(drifted_resources, metadata={"demo": True})


@pytest.fixture
def sample_terraform_plan(tmp_path: Path) -> Path:
    import json

    plan = {
        "resource_changes": [
            {
                "address": "aws_instance.web",
                "type": "aws_instance",
                "name": "web",
                "provider_name": "aws",
                "change": {
                    "actions": ["update"],
                    "before": {"instance_type": "t3.micro"},
                    "after": {"instance_type": "t3.large"},
                },
            },
            {
                "address": "aws_security_group.allow_https",
                "type": "aws_security_group",
                "name": "allow_https",
                "provider_name": "aws",
                "change": {
                    "actions": ["delete", "create"],
                    "before": {"ingress": []},
                    "after": {"ingress": [{"from_port": 443}]},
                },
            },
            {
                "address": "aws_s3_bucket.logs",
                "type": "aws_s3_bucket",
                "name": "logs",
                "provider_name": "aws",
                "change": {
                    "actions": ["create"],
                    "before": None,
                    "after": {"bucket": "my-logs"},
                },
            },
        ]
    }
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan))
    return plan_file
