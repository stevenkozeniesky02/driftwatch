"""DriftWatch CLI interface."""

from __future__ import annotations

import json
import signal
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from driftwatch import __version__
from driftwatch.collectors import detect_available_collectors
from driftwatch.collectors.aws import AWSCollector
from driftwatch.collectors.demo import DemoCollector
from driftwatch.collectors.docker import DockerCollector
from driftwatch.collectors.kubernetes import KubernetesCollector
from driftwatch.collectors.terraform import TerraformCollector
from driftwatch.db import DEFAULT_DB_PATH, Database
from driftwatch.engine.anomaly import AnomalyDetector
from driftwatch.engine.differ import StateDiffer
from driftwatch.engine.predictor import PlanPredictor
from driftwatch.models import ChangeType, CollectorType, DriftSeverity, Snapshot

console = Console()

_COLLECTORS = {
    CollectorType.AWS: AWSCollector,
    CollectorType.TERRAFORM: TerraformCollector,
    CollectorType.DOCKER: DockerCollector,
    CollectorType.KUBERNETES: KubernetesCollector,
}

_SEVERITY_COLORS = {
    DriftSeverity.LOW: "green",
    DriftSeverity.MEDIUM: "yellow",
    DriftSeverity.HIGH: "red",
    DriftSeverity.CRITICAL: "bold red",
}

_CHANGE_COLORS = {
    ChangeType.ADDED: "green",
    ChangeType.REMOVED: "red",
    ChangeType.MODIFIED: "yellow",
}


def _get_db(db_path: str | None) -> Database:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    return Database(path)


def _collect_all(demo: bool) -> list:
    from driftwatch.models import Resource

    if demo:
        collector = DemoCollector()
        resources = collector.collect()
        console.print(f"  [dim]demo[/dim]: {len(resources)} resources", highlight=False)
        return resources

    available = detect_available_collectors()
    if not available:
        console.print("[yellow]No infrastructure tools detected. Use --demo for demo data.[/yellow]")
        return []

    all_resources: list[Resource] = []
    for ct in available:
        collector_cls = _COLLECTORS.get(ct)
        if collector_cls:
            collector = collector_cls()
            resources = collector.collect()
            all_resources.extend(resources)
            console.print(f"  [dim]{ct.value}[/dim]: {len(resources)} resources", highlight=False)
    return all_resources


@click.group()
@click.version_option(__version__, prog_name="driftwatch")
def cli() -> None:
    """Infrastructure drift detector with predictive analysis."""


@cli.command()
@click.option("--demo", is_flag=True, help="Generate fake infrastructure data")
@click.option("--db", "db_path", default=None, help="Path to database file")
def scan(demo: bool, db_path: str | None) -> None:
    """Take a snapshot of current infrastructure state."""
    console.print(Panel.fit("[bold]Scanning infrastructure...[/bold]"))

    resources = _collect_all(demo)
    if not resources:
        return

    snapshot = Snapshot.create(resources, metadata={"demo": demo})
    db = _get_db(db_path)
    db.save_snapshot(snapshot)
    db.close()

    console.print(
        f"\n[green]Snapshot saved:[/green] {snapshot.id} "
        f"({len(resources)} resources at {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')})"
    )


@cli.command()
@click.option("--db", "db_path", default=None, help="Path to database file")
@click.option("--json-output", "as_json", is_flag=True, help="Output as JSON")
def diff(db_path: str | None, as_json: bool) -> None:
    """Compare the last two snapshots and show drift."""
    db = _get_db(db_path)
    snapshots = db.get_latest_snapshots(2)
    if len(snapshots) < 2:
        console.print("[yellow]Need at least 2 snapshots. Run 'driftwatch scan' first.[/yellow]")
        db.close()
        return

    after, before = snapshots[0], snapshots[1]
    differ = StateDiffer()
    result = differ.diff(before, after)
    db.save_diff(result)

    # Anomaly detection
    detector = AnomalyDetector()
    anomalies = detector.analyze([result], snapshots)

    if as_json:
        output = {
            "before": before.id,
            "after": after.id,
            "changes": [
                {
                    "resource_id": c.resource_id,
                    "change_type": c.change_type.value,
                    "field_path": c.field_path,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                }
                for c in result.changes
            ],
            "anomalies": [
                {
                    "resource_id": a.resource_id,
                    "description": a.description,
                    "severity": a.severity.value,
                }
                for a in anomalies
            ],
        }
        click.echo(json.dumps(output, indent=2, default=str))
        db.close()
        return

    console.print(
        Panel.fit(
            f"[bold]Drift Report[/bold]\n"
            f"Before: {before.id} ({before.timestamp.strftime('%H:%M:%S')})\n"
            f"After:  {after.id} ({after.timestamp.strftime('%H:%M:%S')})"
        )
    )

    if not result.changes:
        console.print("[green]No drift detected.[/green]")
    else:
        table = Table(title=f"{len(result.changes)} Changes Detected")
        table.add_column("Type", style="bold", width=10)
        table.add_column("Resource", width=40)
        table.add_column("Field", width=20)
        table.add_column("Change", width=30)

        for c in result.changes:
            color = _CHANGE_COLORS.get(c.change_type, "white")
            change_detail = ""
            if c.old_value is not None or c.new_value is not None:
                change_detail = f"{c.old_value} -> {c.new_value}"
            table.add_row(
                Text(c.change_type.value.upper(), style=color),
                c.resource_id,
                c.field_path or "-",
                change_detail or "-",
            )
        console.print(table)

    if anomalies:
        console.print()
        anomaly_table = Table(title="Anomalies Detected", style="red")
        anomaly_table.add_column("Severity", width=10)
        anomaly_table.add_column("Resource", width=30)
        anomaly_table.add_column("Description", width=50)

        for a in anomalies:
            color = _SEVERITY_COLORS.get(a.severity, "white")
            anomaly_table.add_row(
                Text(a.severity.value.upper(), style=color),
                a.resource_id,
                a.description,
            )
        console.print(anomaly_table)

    db.close()


@cli.command()
@click.option("--db", "db_path", default=None, help="Path to database file")
@click.option("--limit", default=20, help="Number of entries to show")
def history(db_path: str | None, limit: int) -> None:
    """Show timeline of infrastructure changes."""
    db = _get_db(db_path)
    snapshots = db.list_snapshots(limit=limit)

    if not snapshots:
        console.print("[yellow]No snapshots found. Run 'driftwatch scan' first.[/yellow]")
        db.close()
        return

    table = Table(title="Snapshot History")
    table.add_column("ID", style="cyan", width=14)
    table.add_column("Timestamp", width=22)
    table.add_column("Resources", justify="right", width=10)
    table.add_column("Providers", width=30)

    for snap in snapshots:
        providers = sorted({r.provider for r in snap.resources})
        table.add_row(
            snap.id,
            snap.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            str(len(snap.resources)),
            ", ".join(providers),
        )
    console.print(table)
    db.close()


@cli.command()
@click.option("--interval", default="5m", help="Scan interval (e.g. 30s, 5m, 1h)")
@click.option("--demo", is_flag=True, help="Use demo data")
@click.option("--db", "db_path", default=None, help="Path to database file")
def watch(interval: str, demo: bool, db_path: str | None) -> None:
    """Continuously monitor infrastructure for drift."""
    seconds = _parse_interval(interval)
    console.print(
        Panel.fit(f"[bold]Watching for drift every {interval}[/bold]\nPress Ctrl+C to stop")
    )

    running = True

    def _handle_sigint(signum, frame):
        nonlocal running
        running = False
        console.print("\n[yellow]Stopping watch...[/yellow]")

    signal.signal(signal.SIGINT, _handle_sigint)
    iteration = 0

    while running:
        iteration += 1
        console.print(f"\n[dim]--- Scan #{iteration} ---[/dim]")
        resources = _collect_all(demo)
        if not resources:
            break

        snapshot = Snapshot.create(resources, metadata={"demo": demo, "watch": True})
        db = _get_db(db_path)
        db.save_snapshot(snapshot)

        latest = db.get_latest_snapshots(2)
        if len(latest) >= 2:
            differ = StateDiffer()
            result = differ.diff(latest[1], latest[0])
            if result.changes:
                console.print(f"[yellow]Drift detected: {len(result.changes)} changes[/yellow]")
                db.save_diff(result)
            else:
                console.print("[green]No drift.[/green]")
        else:
            console.print("[dim]First scan — baseline recorded.[/dim]")

        db.close()

        for _ in range(seconds * 10):
            if not running:
                break
            time.sleep(0.1)


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--db", "db_path", default=None, help="Path to database file")
def predict(plan_file: str, db_path: str | None) -> None:
    """Predict impact of a Terraform plan on existing infrastructure."""
    db = _get_db(db_path)
    latest = db.get_latest_snapshots(1)
    current = latest[0] if latest else None
    db.close()

    predictor = PlanPredictor()
    try:
        results = predictor.predict(plan_file, current)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    console.print(Panel.fit("[bold]Terraform Plan Impact Analysis[/bold]"))

    table = Table()
    table.add_column("Risk", width=10)
    table.add_column("Description", width=50)
    table.add_column("Affected Resources", width=30)

    for r in results:
        color = _SEVERITY_COLORS.get(r.risk_level, "white")
        affected = ", ".join(r.affected_resources[:3])
        if len(r.affected_resources) > 3:
            affected += f" (+{len(r.affected_resources) - 3} more)"
        table.add_row(
            Text(r.risk_level.value.upper(), style=color),
            r.description,
            affected or "-",
        )
    console.print(table)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--db", "db_path", default=None, help="Path to database file")
def serve(host: str, port: int, db_path: str | None) -> None:
    """Start the web dashboard."""
    import uvicorn

    from driftwatch.web.app import create_app

    db = _get_db(db_path)
    app = create_app(db)
    console.print(
        Panel.fit(f"[bold]DriftWatch Dashboard[/bold]\nhttp://{host}:{port}")
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


def _parse_interval(interval: str) -> int:
    """Parse interval string (30s, 5m, 1h) to seconds."""
    multipliers = {"s": 1, "m": 60, "h": 3600}
    suffix = interval[-1].lower()
    if suffix in multipliers:
        try:
            return int(interval[:-1]) * multipliers[suffix]
        except ValueError:
            pass
    try:
        return int(interval)
    except ValueError:
        raise click.BadParameter(
            f"Invalid interval: {interval}. Use format like 30s, 5m, 1h"
        ) from None
