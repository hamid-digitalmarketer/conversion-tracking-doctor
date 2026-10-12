from conversion_tracking_doctor.analyzers import (
    ClientServerDiscrepancyAnalyzer,
    DuplicateEventsAnalyzer,
    EcommerceSchemaAnalyzer,
    EnhancedConversionsAnalyzer,
    PIILeakAnalyzer,
    ValueCurrencyAnalyzer,
)
from conversion_tracking_doctor.models import (
    ClientEventRow,
    IssueCategory,
    ServerCAPIEventRow,
    Severity,
)


def test_duplicate_events_analyzer():
    events = [
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:00:00Z", transaction_id="ORD-1", value=100.0),
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:00:05Z", transaction_id="ORD-1", value=100.0),
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:01:00Z", transaction_id="ORD-2", value=50.0),
    ]
    analyzer = DuplicateEventsAnalyzer()
    findings = analyzer.analyze(events)

    assert len(findings) == 1
    assert findings[0].category == IssueCategory.DUPLICATE_EVENT
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].entity_value == "ORD-1"
    assert findings[0].occurrence_count == 2


def test_pii_leak_analyzer():
    events = [
        ClientEventRow(
            event_name="page_view",
            timestamp="2026-10-12T10:00:00Z",
            page_location="https://example.com/thanks?email=alex@example.com&phone=555-432-1987",
        )
    ]
    analyzer = PIILeakAnalyzer()
    findings = analyzer.analyze(events)

    assert len(findings) == 2
    categories = {f.category for f in findings}
    assert categories == {IssueCategory.PII_LEAK}
    assert all(f.severity == Severity.CRITICAL for f in findings)


def test_enhanced_conversions_analyzer():
    events = [
        # Unhashed email in user data
        ClientEventRow(
            event_name="purchase",
            timestamp="2026-10-12T10:00:00Z",
            user_data_email="raw_user@example.com",
        ),
        # Malformed uppercase hash
        ClientEventRow(
            event_name="purchase",
            timestamp="2026-10-12T10:01:00Z",
            user_data_email="E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
        ),
    ]
    analyzer = EnhancedConversionsAnalyzer()
    findings = analyzer.analyze(events)

    categories = {f.category for f in findings}
    assert IssueCategory.BROKEN_ENHANCED_CONVERSIONS in categories
    assert any(f.severity == Severity.CRITICAL for f in findings)
    assert any(f.severity == Severity.HIGH for f in findings)


def test_value_currency_analyzer():
    events = [
        # Zero value
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:00:00Z", value=0.0, currency="USD"),
        # Invalid currency
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:01:00Z", value=50.0, currency="US_DOLLARS"),
        # Cents scale anomaly
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:02:00Z", value=19990.0, currency="USD"),
        # Baseline normal purchases
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:03:00Z", value=100.0, currency="USD"),
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:04:00Z", value=120.0, currency="USD"),
    ]
    analyzer = ValueCurrencyAnalyzer()
    findings = analyzer.analyze(events)

    assert len(findings) == 3
    categories = {f.category for f in findings}
    assert categories == {IssueCategory.VALUE_CURRENCY_ANOMALY}


def test_client_server_discrepancy_analyzer():
    client_events = [
        ClientEventRow(event_id=None, event_name="purchase", timestamp="2026-10-12T10:00:00Z", transaction_id="ORD-101"),
        ClientEventRow(event_id="ev-102", event_name="purchase", timestamp="2026-10-12T10:05:00Z", transaction_id="ORD-102"),
    ]
    server_events = [
        ServerCAPIEventRow(
            event_id="ev-102",
            event_name="Purchase",
            timestamp="2026-10-12T10:05:01Z",
            order_id="ORD-102",
            hashed_email="8a1f816409605333f272a74c20b0805125bb7e1140e0be2a09cbbe89b537c352",
            hashed_phone="568e6be57f33be07ee158c35272a85ea82d3e096ffbb79954d71ef69472ee6b0",
        ),
        ServerCAPIEventRow(
            event_id="ev-103",
            event_name="Purchase",
            timestamp="2026-10-12T10:10:01Z",
            order_id="ORD-103",  # Client never tracked this (ad blocker drop-off)
        ),
    ]
    analyzer = ClientServerDiscrepancyAnalyzer()
    findings, overcounting, emq, dropoff = analyzer.analyze(client_events, server_events)

    assert any(f.id == "capi-missing-client-event-id" for f in findings)
    assert dropoff == 50.0  # 1 out of 2 server orders missed by client
    assert emq > 0.0


def test_ecommerce_schema_analyzer():
    events = [
        # Missing transaction_id and missing items
        ClientEventRow(event_name="purchase", timestamp="2026-10-12T10:00:00Z", transaction_id=None, items_count=0),
        # Non-standard event name
        ClientEventRow(event_name="order_completed", timestamp="2026-10-12T10:05:00Z"),
    ]
    analyzer = EcommerceSchemaAnalyzer()
    findings = analyzer.analyze(events)

    assert len(findings) == 3
    assert any(f.id == "schema-missing-transaction-id" for f in findings)
    assert any(f.id == "schema-missing-items-array" for f in findings)
    assert any("order_completed" in f.id for f in findings)
