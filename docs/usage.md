# CLI & Python API Usage Guide

`conversion-tracking-doctor` provides a Typer-powered command-line interface, a standalone FastAPI web dashboard server, and a Python programmatic API.

---

## Command Line Interface (CLI)

### Installation
```bash
git clone https://github.com/hamid-digitalmarketer/conversion-tracking-doctor.git
cd conversion-tracking-doctor
pip install -e ".[dev]"
```

### 1. Run Complete Tracking Health Audit
Run an audit against GA4 browser client events and Meta CAPI server logs:

```bash
conversion-doctor audit \
  --client-events path/to/ga4_client_events.csv \
  --server-events path/to/meta_capi_events.csv \
  --out-dir ./reports \
  --open-browser
```

If no file paths are specified, `conversion-doctor audit` automatically analyzes the built-in realistic sample datasets:
```bash
conversion-doctor audit
```

#### CLI Parameters
| Flag | Short | Default | Description |
|---|---|---|---|
| `--client-events` | `-c` | `sample_data/ga4_client_events.csv` | Path to GA4 / client events CSV |
| `--server-events` | `-s` | `sample_data/meta_capi_events.csv` | Path to Meta CAPI / server events CSV |
| `--out-dir` | `-o` | `./reports` | Output directory for reports and fix snippets |
| `--open-browser` | | `False` | Automatically launch browser with HTML report |

---

### 2. Quick Single URL PII Inspection
Verify whether a redirect URL, thank-you page URL, or campaign link exposes customer emails or telephone numbers in plain text:

```bash
conversion-doctor inspect-url "https://myshop.com/thank-you?order=8812&email=sarah@example.com&phone=5551234567"
```

---

### 3. Launch Local Audit Web Viewer
Browse previously generated audits and review interactive diagnostic cards:

```bash
conversion-doctor serve --port 8000 --host 127.0.0.1
```
Open `http://127.0.0.1:8000` to interact with the dashboard.

---

## Python Programmatic API

Embed `conversion-tracking-doctor` into automated CI/CD pipelines, tag testing suites, or scheduled data warehouse checks:

```python
from pathlib import Path
from data.loader import load_client_events, load_server_events
from conversion_tracking_doctor.analyzers import (
    DuplicateEventsAnalyzer,
    PIILeakAnalyzer,
    EnhancedConversionsAnalyzer,
    ValueCurrencyAnalyzer,
    EcommerceSchemaAnalyzer,
    ClientServerDiscrepancyAnalyzer,
)
from conversion_tracking_doctor.report import ReportGenerator
from conversion_tracking_doctor.storage import SQLiteStorage
from conversion_tracking_doctor.models import DoctorAudit, TrackingHealthSummary

# Load event streams
client_rows = load_client_events("data/sample_data/ga4_client_events.csv")
server_rows = load_server_events("data/sample_data/meta_capi_events.csv")

# Run diagnostic engines
findings = []
findings.extend(DuplicateEventsAnalyzer().analyze(client_rows))
findings.extend(PIILeakAnalyzer().analyze(client_rows))
findings.extend(EnhancedConversionsAnalyzer().analyze(client_rows))
findings.extend(ValueCurrencyAnalyzer().analyze(client_rows))
findings.extend(EcommerceSchemaAnalyzer().analyze(client_rows))

disc_findings, overcounting_pct, emq_score, dropoff_pct = (
    ClientServerDiscrepancyAnalyzer().analyze(client_rows, server_rows)
)
findings.extend(disc_findings)

# Build summary and export
summary = TrackingHealthSummary(
    total_events_analyzed=len(client_rows) + len(server_rows),
    total_issues_found=len(findings),
    critical_count=sum(1 for f in findings if f.severity.value == "CRITICAL"),
    high_count=sum(1 for f in findings if f.severity.value == "HIGH"),
    medium_count=sum(1 for f in findings if f.severity.value == "MEDIUM"),
    low_count=sum(1 for f in findings if f.severity.value == "LOW"),
    estimated_overcounting_pct=overcounting_pct,
    event_match_quality_score=emq_score,
    ad_blocker_dropoff_pct=dropoff_pct,
)

audit = DoctorAudit(
    audit_id="manual-api-audit",
    created_at="2026-10-12T10:00:00Z",
    summary=summary,
    findings=findings,
)

reporter = ReportGenerator(output_dir=Path("./reports"))
paths = reporter.generate_all(audit)
print(f"Generated HTML report at: {paths['html']}")
```

---

## Exported Artifacts

- **`reports/audit-<timestamp>-<hash>.html`**: Standalone Tailwind CSS interactive dashboard.
- **`reports/audit-<timestamp>-<hash>.json`**: Machine-readable JSON summary.
- **`reports/audit-<timestamp>-<hash>.csv`**: Flat CSV table of all findings.
- **`reports/gtm_transaction_deduplication.js`**: Ready-to-paste GTM Custom JS Variable for localStorage deduplication.
- **`reports/gtm_pii_scrubber.js`**: Ready-to-paste GTM Custom JS Variable to redact query string emails/phones.
- **`reports/meta_capi_remediation.py`**: Python reference script for resilient CAPI dispatches.
