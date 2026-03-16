"""AWS infrastructure collector using AWS CLI."""

from __future__ import annotations

import json

from driftwatch.collectors.base import BaseCollector, _has_command
from driftwatch.models import CollectorType, Resource


class AWSCollector(BaseCollector):
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.AWS

    def is_available(self) -> bool:
        return _has_command("aws")

    def collect(self) -> list[Resource]:
        resources: list[Resource] = []
        resources.extend(self._collect_ec2_instances())
        resources.extend(self._collect_security_groups())
        resources.extend(self._collect_s3_buckets())
        return resources

    def _collect_ec2_instances(self) -> list[Resource]:
        output = self._run_command(
            ["aws", "ec2", "describe-instances", "--output", "json"]
        )
        if not output:
            return []
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        resources = []
        for reservation in data.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                name = _get_tag(instance, "Name") or instance["InstanceId"]
                resources.append(
                    Resource(
                        type="ec2_instance",
                        name=name,
                        provider="aws",
                        properties={
                            "instance_id": instance["InstanceId"],
                            "instance_type": instance.get("InstanceType"),
                            "state": instance.get("State", {}).get("Name"),
                            "vpc_id": instance.get("VpcId"),
                            "subnet_id": instance.get("SubnetId"),
                            "security_groups": [
                                sg["GroupId"]
                                for sg in instance.get("SecurityGroups", [])
                            ],
                        },
                    )
                )
        return resources

    def _collect_security_groups(self) -> list[Resource]:
        output = self._run_command(
            ["aws", "ec2", "describe-security-groups", "--output", "json"]
        )
        if not output:
            return []
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        resources = []
        for sg in data.get("SecurityGroups", []):
            resources.append(
                Resource(
                    type="security_group",
                    name=sg.get("GroupName", sg["GroupId"]),
                    provider="aws",
                    properties={
                        "group_id": sg["GroupId"],
                        "vpc_id": sg.get("VpcId"),
                        "ingress_rules": len(sg.get("IpPermissions", [])),
                        "egress_rules": len(sg.get("IpPermissionsEgress", [])),
                        "description": sg.get("Description", ""),
                    },
                    dependencies=(f"aws/vpc/{sg.get('VpcId', 'unknown')}",),
                )
            )
        return resources

    def _collect_s3_buckets(self) -> list[Resource]:
        output = self._run_command(["aws", "s3api", "list-buckets", "--output", "json"])
        if not output:
            return []
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        return [
            Resource(
                type="s3_bucket",
                name=b["Name"],
                provider="aws",
                properties={"creation_date": b.get("CreationDate", "")},
            )
            for b in data.get("Buckets", [])
        ]


def _get_tag(resource: dict, key: str) -> str | None:
    for tag in resource.get("Tags", []):
        if tag.get("Key") == key:
            return tag.get("Value")
    return None
