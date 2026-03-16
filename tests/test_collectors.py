"""Tests for collectors."""

from driftwatch.collectors.demo import DemoCollector, _call_count
from driftwatch.collectors.base import detect_available_collectors
from driftwatch.collectors.terraform import parse_terraform_plan


class TestDemoCollector:
    def test_collect_returns_resources(self):
        collector = DemoCollector(seed=42)
        resources = collector.collect()
        assert len(resources) > 0

    def test_is_always_available(self):
        collector = DemoCollector()
        assert collector.is_available() is True

    def test_resources_have_required_fields(self):
        collector = DemoCollector(seed=42)
        resources = collector.collect()
        for r in resources:
            assert r.type
            assert r.name
            assert r.provider

    def test_multiple_providers_present(self):
        collector = DemoCollector(seed=42)
        resources = collector.collect()
        providers = {r.provider for r in resources}
        assert len(providers) >= 2

    def test_multiple_resource_types(self):
        collector = DemoCollector(seed=42)
        resources = collector.collect()
        types = {r.type for r in resources}
        assert len(types) >= 3

    def test_drift_between_calls(self):
        collector = DemoCollector(seed=100)
        first = collector.collect()
        second = collector.collect()
        # Resources may differ due to drift simulation
        first_ids = {r.id for r in first}
        second_ids = {r.id for r in second}
        first_props = {r.id: r.properties for r in first}
        second_props = {r.id: r.properties for r in second}
        # Either IDs differ or properties differ
        ids_differ = first_ids != second_ids
        props_differ = any(
            first_props.get(rid) != second_props.get(rid)
            for rid in first_ids & second_ids
        )
        assert ids_differ or props_differ


class TestDetectAvailableCollectors:
    def test_returns_list(self):
        result = detect_available_collectors()
        assert isinstance(result, list)


class TestParseTerraformPlan:
    def test_parse_valid_plan(self):
        plan = {
            "resource_changes": [
                {
                    "address": "aws_instance.web",
                    "type": "aws_instance",
                    "name": "web",
                    "change": {
                        "actions": ["update"],
                        "before": {"instance_type": "t3.micro"},
                        "after": {"instance_type": "t3.large"},
                    },
                }
            ]
        }
        changes = parse_terraform_plan(plan)
        assert len(changes) == 1
        assert changes[0]["address"] == "aws_instance.web"
        assert "update" in changes[0]["actions"]

    def test_parse_empty_plan(self):
        changes = parse_terraform_plan({"resource_changes": []})
        assert changes == []

    def test_parse_plan_no_changes_key(self):
        changes = parse_terraform_plan({})
        assert changes == []
