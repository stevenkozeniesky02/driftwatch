"""Tests for the CLI interface."""

from pathlib import Path

from click.testing import CliRunner

from driftwatch.cli import _parse_interval, cli
from driftwatch.db import Database
from driftwatch.models import Resource, Snapshot

import pytest


class TestParseInterval:
    def test_seconds(self):
        assert _parse_interval("30s") == 30

    def test_minutes(self):
        assert _parse_interval("5m") == 300

    def test_hours(self):
        assert _parse_interval("1h") == 3600

    def test_plain_number(self):
        assert _parse_interval("60") == 60

    def test_invalid_raises(self):
        from click import BadParameter
        with pytest.raises(BadParameter):
            _parse_interval("abc")


class TestScanCommand:
    def test_scan_demo(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--demo", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "Snapshot saved" in result.output

        db = Database(db_path)
        assert db.snapshot_count() == 1
        db.close()

    def test_scan_no_tools(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--db", str(db_path)])
        # Should either find tools or warn
        assert result.exit_code == 0


class TestDiffCommand:
    def test_diff_needs_two_snapshots(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        runner = CliRunner()
        result = runner.invoke(cli, ["diff", "--db", str(db_path)])
        assert "Need at least 2 snapshots" in result.output

    def test_diff_with_data(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        runner = CliRunner()
        # Two scans to get diff data
        runner.invoke(cli, ["scan", "--demo", "--db", str(db_path)])
        runner.invoke(cli, ["scan", "--demo", "--db", str(db_path)])
        result = runner.invoke(cli, ["diff", "--db", str(db_path)])
        assert result.exit_code == 0

    def test_diff_json_output(self, tmp_path: Path):
        import json

        db_path = tmp_path / "test.db"
        runner = CliRunner()
        runner.invoke(cli, ["scan", "--demo", "--db", str(db_path)])
        runner.invoke(cli, ["scan", "--demo", "--db", str(db_path)])
        result = runner.invoke(cli, ["diff", "--db", str(db_path), "--json-output"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "changes" in data
        assert "anomalies" in data


class TestHistoryCommand:
    def test_history_empty(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--db", str(db_path)])
        assert "No snapshots found" in result.output

    def test_history_with_data(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        runner = CliRunner()
        runner.invoke(cli, ["scan", "--demo", "--db", str(db_path)])
        result = runner.invoke(cli, ["history", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "Snapshot History" in result.output


class TestPredictCommand:
    def test_predict(self, sample_terraform_plan: Path, tmp_path: Path):
        db_path = tmp_path / "test.db"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["predict", str(sample_terraform_plan), "--db", str(db_path)]
        )
        assert result.exit_code == 0
        assert "Impact Analysis" in result.output

    def test_predict_missing_file(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(cli, ["predict", "/nonexistent/plan.json"])
        assert result.exit_code != 0


class TestVersionOption:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert "0.1.0" in result.output
