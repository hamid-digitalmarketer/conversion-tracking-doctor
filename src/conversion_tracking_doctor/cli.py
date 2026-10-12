import datetime
import hashlib
import sys
import webbrowser
from pathlib import Path
from typing import List, Optional

import typer
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from conversion_tracking_doctor.analyzers import (
    ClientServerDiscrepancyAnalyzer,
    DuplicateEventsAnalyzer,
    EcommerceSchemaAnalyzer,
    EnhancedConversionsAnalyzer,
    PIILeakAnalyzer,
    ValueCurrencyAnalyzer,
)
from conversion_tracking_doctor.exporters import CAPIRemediationExporter, GTMSnippetExporter
from conversion_tracking_doctor.models import (
    DiagnosticFinding,
    DoctorAudit,
    Severity,
    TrackingHealthSummary,
)
from conversion_tracking_doctor.report import ReportGenerator
from conversion_tracking_doctor.storage import SQLiteStorage
from data.loader import load_client_events, load_server_events

app = typer.Typer(
    name="conversion-doctor",
    help="Conversion Tracking Doctor: Web Analytics & CAPI Diagnostic Health Engine.",
)
console = Console()


@app.command()
def audit(
    client_events: Optional[Path] = typer.Option(
        None,
        "--client-events",
        "-c",
        help="Path to GA4 / Browser Client Events CSV. Uses built-in sample data if omitted.",
    ),
    server_events: Optional[Path] = typer.Option(
        None,
        "--server-events",
        "-s",
        help="Path to Meta CAPI / Server Events CSV. Uses built-in sample data if omitted.",
    ),
    out_dir: Path = typer.Option(
        Path("reports"),
        "--out-dir",
        "-o",
        help="Directory to save audit reports and remediation snippets.",
    ),
    open_browser: bool = typer.Option(
        False,
        "--open-browser",
        help="Automatically open the interactive HTML audit report in default browser.",
    ),
) -> None:
    """Run an end-to-end tracking health diagnostic audit."""
    console.print(
        Panel.fit(
            "[bold cyan]Conversion Tracking Doctor[/bold cyan]\n"
            "[dim]Auditing client-side GA4 events & server-side Meta CAPI data streams...[/dim]",
            border_style="cyan",
        )
    )

    base_dir = Path(__file__).resolve().parent.parent.parent
    sample_dir = base_dir / "data" / "sample_data"

    if client_events is None:
        client_events = sample_dir / "ga4_client_events.csv"
        console.print("[yellow]Notice:[/yellow] No client events file provided. Using built-in sample dataset.")

    if server_events is None:
        server_events = sample_dir / "meta_capi_events.csv"
        console.print("[yellow]Notice:[/yellow] No server events file provided. Using built-in sample dataset.")

    if not client_events.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {client_events}")
        sys.exit(1)

    c_rows = load_client_events(client_events)
    s_rows = load_server_events(server_events) if server_events.exists() else []

    all_findings: List[DiagnosticFinding] = []

    # Run Analyzers
    with console.status("[bold green]Running diagnostic analyzers..."):
        all_findings.extend(DuplicateEventsAnalyzer().analyze(c_rows))
        all_findings.extend(PIILeakAnalyzer().analyze(c_rows))
        all_findings.extend(EnhancedConversionsAnalyzer().analyze(c_rows))
        all_findings.extend(ValueCurrencyAnalyzer().analyze(c_rows))
        all_findings.extend(EcommerceSchemaAnalyzer().analyze(c_rows))

        discrepancy_findings, overcounting_pct, emq_score, dropoff_pct = (
            ClientServerDiscrepancyAnalyzer().analyze(c_rows, s_rows)
        )
        all_findings.extend(discrepancy_findings)

    # Sort findings by severity
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    all_findings.sort(key=lambda f: severity_order[f.severity])

    # Summary counts
    crit = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
    high = sum(1 for f in all_findings if f.severity == Severity.HIGH)
    med = sum(1 for f in all_findings if f.severity == Severity.MEDIUM)
    low = sum(1 for f in all_findings if f.severity == Severity.LOW)

    total_events = len(c_rows) + len(s_rows)
    summary = TrackingHealthSummary(
        total_events_analyzed=total_events,
        total_issues_found=len(all_findings),
        critical_count=crit,
        high_count=high,
        medium_count=med,
        low_count=low,
        estimated_overcounting_pct=overcounting_pct,
        event_match_quality_score=emq_score,
        ad_blocker_dropoff_pct=dropoff_pct,
    )

    audit_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    audit_hash = hashlib.md5(f"{audit_timestamp}-{len(all_findings)}".encode()).hexdigest()[:6]
    audit_id = f"{audit_timestamp}-{audit_hash}"

    audit_result = DoctorAudit(
        audit_id=audit_id,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        summary=summary,
        findings=all_findings,
    )

    # Save to SQLite and export reports
    storage = SQLiteStorage(out_dir / "tracking_doctor.sqlite")
    storage.save_audit(audit_result)

    reporter = ReportGenerator(output_dir=out_dir)
    report_paths = reporter.generate_all(audit_result)

    # Export GTM and CAPI code fixes
    gtm_paths = GTMSnippetExporter(out_dir).export_all()
    capi_paths = CAPIRemediationExporter(out_dir).export_all()

    # Display KPI Table
    kpi_table = Table(title="Tracking Health Audit Summary", border_style="blue")
    kpi_table.add_column("Metric", style="bold")
    kpi_table.add_column("Value", style="cyan")

    kpi_table.add_row("Total Events Processed", str(total_events))
    kpi_table.add_row("Total Diagnostic Issues", f"[bold red]{len(all_findings)}[/bold red]")
    kpi_table.add_row("Critical Severity", f"[bold red]{crit}[/bold red]")
    kpi_table.add_row("High Severity", f"[bold yellow]{high}[/bold yellow]")
    kpi_table.add_row("Medium / Low", f"{med + low}")
    kpi_table.add_row("Est. Duplicate Overcounting", f"[bold red]{overcounting_pct}%[/bold red]")
    kpi_table.add_row("Meta CAPI Match Quality (EMQ)", f"[bold cyan]{emq_score} / 10[/bold cyan]")
    kpi_table.add_row("Ad-Blocker / iOS Signal Loss", f"[bold magenta]{dropoff_pct}%[/bold magenta]")
    console.print(kpi_table)

    # Display Top Findings Table
    findings_table = Table(title="Detected Tracking Issues & Leaks", border_style="cyan")
    findings_table.add_column("Severity", style="bold")
    findings_table.add_column("Category", style="dim")
    findings_table.add_column("Issue Title")
    findings_table.add_column("Occurrences", justify="right")

    for f in all_findings:
        sev_color = {
            Severity.CRITICAL: "red",
            Severity.HIGH: "yellow",
            Severity.MEDIUM: "blue",
            Severity.LOW: "white",
            Severity.INFO: "dim",
        }.get(f.severity, "white")

        findings_table.add_row(
            f"[{sev_color}]{f.severity.value}[/{sev_color}]",
            f.category.value,
            f.title,
            str(f.occurrence_count),
        )

    console.print(findings_table)

    console.print(
        Panel.fit(
            f"[bold green]Audit Complete![/bold green]\n\n"
            f"- Interactive HTML Report: [cyan]{report_paths['html']}[/cyan]\n"
            f"- Machine-readable JSON:  [dim]{report_paths['json']}[/dim]\n"
            f"- Flat CSV Findings:      [dim]{report_paths['csv']}[/dim]\n"
            f"- GTM Deduplication JS:   [dim]{gtm_paths['gtm_dedup']}[/dim]\n"
            f"- GTM PII Scrubber JS:    [dim]{gtm_paths['gtm_pii']}[/dim]\n"
            f"- CAPI Python Template:   [dim]{capi_paths['capi_python']}[/dim]",
            border_style="green",
        )
    )

    if open_browser:
        webbrowser.open(report_paths["html"].resolve().as_uri())


@app.command()
def inspect_url(
    url: str = typer.Argument(..., help="Web page URL or thank-you page URL to inspect for PII and parameter issues.")
) -> None:
    """Quickly inspect a single URL or query string for unhashed PII leaks."""
    from conversion_tracking_doctor.models import ClientEventRow

    dummy_event = ClientEventRow(
        event_name="page_view",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        page_location=url,
    )
    findings = PIILeakAnalyzer().analyze([dummy_event])

    if not findings:
        console.print(f"[bold green]PASSED:[/bold green] No plaintext email or phone number detected in URL:\n[dim]{url}[/dim]")
    else:
        console.print(f"[bold red]PRIVACY ALERT:[/bold red] Found {len(findings)} unhashed PII leaks in URL:")
        for f in findings:
            console.print(f"  - [{f.severity.value}] {f.title}: [red]{f.entity_value}[/red]")
            console.print(f"    Impact: {f.impact}")
            console.print(f"    Fix:    {f.recommended_fix}\n")


@app.command()
def serve(
    db_path: Path = typer.Option(
        Path("reports/tracking_doctor.sqlite"),
        "--db-path",
        help="Path to SQLite audit database.",
    ),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run web server on."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface."),
) -> None:
    """Launch local web server to browse the latest conversion tracking audit report."""
    server_app = FastAPI(title="Conversion Tracking Doctor Web Viewer")

    @server_app.get("/", response_class=HTMLResponse)
    def index() -> str:
        storage = SQLiteStorage(db_path)
        audit = storage.get_latest_audit()
        if not audit:
            raise HTTPException(
                status_code=404,
                detail="No audit found in database. Run 'conversion-doctor audit' first.",
            )
        template_dir = Path(__file__).parent / "templates"
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
        return env.get_template("report.html").render(audit=audit)

    console.print(f"[bold green]Starting viewer on http://{host}:{port}...[/bold green]")
    uvicorn.run(server_app, host=host, port=port)


@app.command()
def version() -> None:
    """Display current version of Conversion Tracking Doctor."""
    console.print("[bold cyan]conversion-tracking-doctor[/bold cyan] version [bold white]0.1.0[/bold white]")


if __name__ == "__main__":
    app()
