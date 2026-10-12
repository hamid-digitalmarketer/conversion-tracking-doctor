from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class IssueCategory(str, Enum):
    DUPLICATE_EVENT = "duplicate_event"
    PII_LEAK = "pii_leak"
    BROKEN_ENHANCED_CONVERSIONS = "broken_enhanced_conversions"
    VALUE_CURRENCY_ANOMALY = "value_currency_anomaly"
    CLIENT_SERVER_DISCREPANCY = "client_server_discrepancy"
    MISSING_ECOMMERCE_SCHEMA = "missing_ecommerce_schema"


class DiagnosticFinding(BaseModel):
    id: str
    category: IssueCategory
    severity: Severity
    title: str
    description: str
    entity_type: str
    entity_value: str
    impact: str
    recommended_fix: str
    occurrence_count: int = 1
    sample_payload: Optional[Dict[str, Any]] = None


class ClientEventRow(BaseModel):
    event_id: Optional[str] = None
    event_name: str
    timestamp: str
    transaction_id: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    page_location: Optional[str] = None
    user_data_email: Optional[str] = None
    user_data_phone: Optional[str] = None
    items_count: Optional[int] = None
    custom_parameters: Optional[str] = None


class ServerCAPIEventRow(BaseModel):
    event_id: Optional[str] = None
    event_name: str
    timestamp: str
    order_id: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    hashed_email: Optional[str] = None
    hashed_phone: Optional[str] = None
    action_source: Optional[str] = "website"


class TrackingHealthSummary(BaseModel):
    total_events_analyzed: int
    total_issues_found: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int = 0
    estimated_overcounting_pct: float = 0.0
    event_match_quality_score: float = 0.0  # 0 to 10
    ad_blocker_dropoff_pct: float = 0.0


class DoctorAudit(BaseModel):
    audit_id: str
    created_at: str
    summary: TrackingHealthSummary
    findings: List[DiagnosticFinding] = Field(default_factory=list)
