# DriftWatch

**Infrastructure drift detector with predictive analysis.**

DriftWatch takes periodic snapshots of your cloud infrastructure state, compares them to detect drift, flags anomalies, and predicts the impact of planned changes.

## Features

- **Multi-provider scanning** — Automatically detects and collects state from AWS CLI, Terraform, Docker, and Kubernetes
- **State diffing** — Side-by-side comparison of any two snapshots with field-level change tracking
- **Anomaly detection** — Flags unexpected changes, security drift, off-hours modifications, and resource churn
- **Terraform plan prediction** — Parse a `terraform plan` JSON and predict which existing resources will be affected
- **Web dashboard** — Timeline view, visual diffs, alert feed, and resource dependency graph
- **Demo mode** — Try everything without cloud credentials using realistic fake infrastructure

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Take a demo snapshot
driftwatch scan --demo

# Take another (drift will be simulated)
driftwatch scan --demo

# See what changed
driftwatch diff

# View history
driftwatch history

# Start the dashboard
driftwatch serve
# Open http://127.0.0.1:8000
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `driftwatch scan` | Take a snapshot of current infrastructure |
| `driftwatch scan --demo` | Generate fake infrastructure data |
| `driftwatch diff` | Compare the last two snapshots |
| `driftwatch diff --json-output` | Output diff as JSON |
| `driftwatch history` | Show snapshot timeline |
| `driftwatch watch --interval 5m` | Continuous monitoring mode |
| `driftwatch predict plan.json` | Predict Terraform plan impact |
| `driftwatch serve` | Start the web dashboard |

## Web Dashboard

Start with `driftwatch serve` and open `http://127.0.0.1:8000`.

- **Timeline** — Browse all snapshots with resource counts and provider badges
- **Diff Viewer** — Select any two snapshots for side-by-side comparison with color-coded changes
- **Alerts** — Severity-ranked anomalies: security drift, unexpected resources, churn detection
- **Dependency Graph** — Visual map of resource relationships within a snapshot

## Demo Mode

The `--demo` flag generates realistic infrastructure that mutates between scans:

```bash
# Generate several snapshots with drift
for i in $(seq 1 5); do driftwatch scan --demo; sleep 1; done

# See the drift
driftwatch diff

# Or watch continuously
driftwatch watch --interval 10s --demo
```

Demo simulates:
- Security group rule changes
- Instance type mutations
- Container image version drift
- Kubernetes replica scaling
- Mystery instances appearing
- Resources disappearing

## Terraform Plan Analysis

```bash
# Generate a plan
terraform plan -out=plan.tfplan
terraform show -json plan.tfplan > plan.json

# Predict impact
driftwatch predict plan.json
```

DriftWatch will flag:
- Destructive actions (delete, replace) as **CRITICAL**
- Security-sensitive resource changes as **HIGH**
- Dependency chain impacts as **MEDIUM**
- Overall risk summary

## Docker

```bash
# Build and run
docker compose up -d

# Or build manually
docker build -t driftwatch .
docker run -p 8000:8000 driftwatch
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=driftwatch --cov-report=term-missing

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

## Architecture

```
src/driftwatch/
├── cli.py                 # Click CLI commands
├── db.py                  # SQLite backend (JSON snapshots)
├── models.py              # Immutable domain models
├── collectors/
│   ├── base.py            # Collector interface + discovery
│   ├── aws.py             # AWS CLI collector
│   ├── terraform.py       # Terraform state collector
│   ├── docker.py          # Docker container collector
│   ├── kubernetes.py      # Kubernetes resource collector
│   └── demo.py            # Fake data generator with drift simulation
├── engine/
│   ├── differ.py          # State diffing with DeepDiff
│   ├── anomaly.py         # Pattern-based anomaly detection
│   └── predictor.py       # Terraform plan impact predictor
└── web/
    ├── app.py             # FastAPI application
    ├── routes.py           # API endpoints
    └── static/             # Dashboard (vanilla HTML/JS/CSS)
```

## License

MIT
