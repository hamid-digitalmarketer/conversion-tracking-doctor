import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from conversion_tracking_doctor.models import (
    DiagnosticFinding,
    DoctorAudit,
    IssueCategory,
    Severity,
    TrackingHealthSummary,
)


class SQLiteStorage:
    def __init__(self, db_path: str | Path = "reports/tracking_doctor.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audits (
                    audit_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    total_events_analyzed INTEGER,
                    total_issues_found INTEGER,
                    critical_count INTEGER,
                    high_count INTEGER,
                    medium_count INTEGER,
                    low_count INTEGER,
                    estimated_overcounting_pct REAL,
                    event_match_quality_score REAL,
                    ad_blocker_dropoff_pct REAL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    audit_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL,
                    impact TEXT NOT NULL,
                    recommended_fix TEXT NOT NULL,
                    occurrence_count INTEGER DEFAULT 1,
                    sample_payload TEXT,
                    FOREIGN KEY (audit_id) REFERENCES audits (audit_id)
                )
                """
            )
            conn.commit()

    def save_audit(self, audit: DoctorAudit) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO audits (
                    audit_id, created_at, total_events_analyzed, total_issues_found,
                    critical_count, high_count, medium_count, low_count,
                    estimated_overcounting_pct, event_match_quality_score, ad_blocker_dropoff_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit.audit_id,
                    audit.created_at,
                    audit.summary.total_events_analyzed,
                    audit.summary.total_issues_found,
                    audit.summary.critical_count,
                    audit.summary.high_count,
                    audit.summary.medium_count,
                    audit.summary.low_count,
                    audit.summary.estimated_overcounting_pct,
                    audit.summary.event_match_quality_score,
                    audit.summary.ad_blocker_dropoff_pct,
                ),
            )
            for f in audit.findings:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO findings (
                        id, audit_id, category, severity, title, description,
                        entity_type, entity_value, impact, recommended_fix,
                        occurrence_count, sample_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f.id,
                        audit.audit_id,
                        f.category.value,
                        f.severity.value,
                        f.title,
                        f.description,
                        f.entity_type,
                        f.entity_value,
                        f.impact,
                        f.recommended_fix,
                        f.occurrence_count,
                        json.dumps(f.sample_payload) if f.sample_payload else None,
                    ),
                )
            conn.commit()

    def get_latest_audit(self) -> Optional[DoctorAudit]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audits ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None

            audit_id = row["audit_id"]
            cursor.execute("SELECT * FROM findings WHERE audit_id = ?", (audit_id,))
            finding_rows = cursor.fetchall()

            findings: List[DiagnosticFinding] = []
            for fr in finding_rows:
                findings.append(
                    DiagnosticFinding(
                        id=fr["id"],
                        category=IssueCategory(fr["category"]),
                        severity=Severity(fr["severity"]),
                        title=fr["title"],
                        description=fr["description"],
                        entity_type=fr["entity_type"],
                        entity_value=fr["entity_value"],
                        impact=fr["impact"],
                        recommended_fix=fr["recommended_fix"],
                        occurrence_count=fr["occurrence_count"],
                        sample_payload=json.loads(fr["sample_payload"]) if fr["sample_payload"] else None,
                    )
                )

            summary = TrackingHealthSummary(
                total_events_analyzed=row["total_events_analyzed"],
                total_issues_found=row["total_issues_found"],
                critical_count=row["critical_count"],
                high_count=row["high_count"],
                medium_count=row["medium_count"],
                low_count=row["low_count"],
                estimated_overcounting_pct=row["estimated_overcounting_pct"],
                event_match_quality_score=row["event_match_quality_score"],
                ad_blocker_dropoff_pct=row["ad_blocker_dropoff_pct"],
            )

            return DoctorAudit(
                audit_id=audit_id,
                created_at=row["created_at"],
                summary=summary,
                findings=findings,
            )
