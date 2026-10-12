from pathlib import Path

from conversion_tracking_doctor.models import (
    DiagnosticFinding,
    DoctorAudit,
    IssueCategory,
    Severity,
    TrackingHealthSummary,
)
from conversion_tracking_doctor.report import ReportGenerator


def test_generate_reports(tmp_path: Path):
    finding = DiagnosticFinding(
        id="test-1",
        category=IssueCategory.DUPLICATE_EVENT,
        severity=Severity.CRITICAL,
        title="Duplicate Purchase Event",
        description="Fired twice",
        entity_type="transaction_id",
        entity_value="TXN-999",
        impact="Overcounting revenue",
        recommended_fix="Deduplicate via GTM",
        occurrence_count=2,
    )
    summary = TrackingHealthSummary(
        total_events_analyzed=10,
        total_issues_found=1,
        critical_count=1,
        high_count=0,
        medium_count=0,
        low_count=0,
        estimated_overcounting_pct=10.0,
        event_match_quality_score=8.5,
        ad_blocker_dropoff_pct=15.0,
    )
    audit = DoctorAudit(
        audit_id="audit-test-123",
        created_at="2026-10-12T10:00:00Z",
        summary=summary,
        findings=[finding],
    )

    reporter = ReportGenerator(tmp_path)
    res = reporter.generate_all(audit)

    assert res["html"].exists()
    assert res["json"].exists()
    assert res["csv"].exists()

    html_content = res["html"].read_text(encoding="utf-8")
    assert "audit-test-123" in html_content
    assert "Duplicate Purchase Event" in html_content
    assert "CRITICAL" in html_content
