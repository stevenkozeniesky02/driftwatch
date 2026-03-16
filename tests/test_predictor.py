"""Tests for the plan predictor."""

from pathlib import Path

import pytest

from driftwatch.engine.predictor import PlanPredictor
from driftwatch.models import DriftSeverity, Resource, Snapshot


class TestPlanPredictor:
    def test_predict_from_plan(self, sample_terraform_plan: Path):
        predictor = PlanPredictor()
        results = predictor.predict(sample_terraform_plan)
        assert len(results) > 0

    def test_destructive_changes_flagged(self, sample_terraform_plan: Path):
        predictor = PlanPredictor()
        results = predictor.predict(sample_terraform_plan)
        critical = [r for r in results if r.risk_level == DriftSeverity.CRITICAL]
        assert len(critical) > 0
        # The security group has delete action
        sg_critical = [r for r in critical if "security_group" in str(r.affected_resources)]
        assert len(sg_critical) > 0

    def test_security_sensitive_flagged(self, sample_terraform_plan: Path):
        predictor = PlanPredictor()
        results = predictor.predict(sample_terraform_plan)
        high = [r for r in results if r.risk_level == DriftSeverity.HIGH]
        assert len(high) > 0

    def test_summary_generated(self, sample_terraform_plan: Path):
        predictor = PlanPredictor()
        results = predictor.predict(sample_terraform_plan)
        summaries = [r for r in results if "summary" in r.description.lower()]
        assert len(summaries) == 1

    def test_dependency_impact(self, sample_terraform_plan: Path, sample_resources: list[Resource]):
        snapshot = Snapshot.create(sample_resources)
        predictor = PlanPredictor()
        results = predictor.predict(sample_terraform_plan, snapshot)
        assert len(results) > 0

    def test_empty_plan(self, tmp_path: Path):
        plan_file = tmp_path / "empty.json"
        plan_file.write_text('{"resource_changes": []}')
        predictor = PlanPredictor()
        results = predictor.predict(plan_file)
        assert len(results) == 1
        assert results[0].risk_level == DriftSeverity.LOW

    def test_missing_file_raises(self):
        predictor = PlanPredictor()
        with pytest.raises(FileNotFoundError):
            predictor.predict("/nonexistent/plan.json")

    def test_invalid_json_raises(self, tmp_path: Path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json")
        predictor = PlanPredictor()
        with pytest.raises(ValueError, match="Invalid JSON"):
            predictor.predict(bad_file)

    def test_plan_with_no_resource_changes_key(self, tmp_path: Path):
        plan_file = tmp_path / "minimal.json"
        plan_file.write_text("{}")
        predictor = PlanPredictor()
        results = predictor.predict(plan_file)
        assert len(results) == 1
        assert results[0].risk_level == DriftSeverity.LOW
