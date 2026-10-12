from typing import List, Tuple

from conversion_tracking_doctor.models import (
    ClientEventRow,
    DiagnosticFinding,
    IssueCategory,
    ServerCAPIEventRow,
    Severity,
)


class ClientServerDiscrepancyAnalyzer:
    """Analyzes differences between browser client events and server-side CAPI logs."""

    def analyze(
        self, client_events: List[ClientEventRow], server_events: List[ServerCAPIEventRow]
    ) -> Tuple[List[DiagnosticFinding], float, float, float]:
        """
        Returns:
            (findings, overcounting_pct, emq_score, ad_blocker_dropoff_pct)
        """
        findings: List[DiagnosticFinding] = []

        client_purchases = [
            e for e in client_events if e.event_name.lower() in ("purchase", "ecommerce_purchase")
        ]
        server_purchases = [
            e for e in server_events if e.event_name.lower() in ("purchase", "ecommerce_purchase")
        ]

        # 1. Missing event_id in client events
        missing_client_event_id = sum(1 for e in client_purchases if not e.event_id)
        if client_purchases and (missing_client_event_id / len(client_purchases)) > 0.2:
            pct_missing = (missing_client_event_id / len(client_purchases)) * 100
            findings.append(
                DiagnosticFinding(
                    id="capi-missing-client-event-id",
                    category=IssueCategory.CLIENT_SERVER_DISCREPANCY,
                    severity=Severity.CRITICAL,
                    title="Missing event_id on Browser Client Conversion Tags",
                    description=(
                        f"{missing_client_event_id} of {len(client_purchases)} ({pct_missing:.1f}%) browser conversion events "
                        "lack a unique event_id parameter. Without matching event_id values, Meta and Google cannot deduplicate "
                        "browser pixel hits from server CAPI hits."
                    ),
                    entity_type="event_id_deduplication",
                    entity_value="event_id=None",
                    impact=(
                        "Causes double-counting of conversions whenever both browser and server tags fire. "
                        "Inflates conversion metrics by up to 100%."
                    ),
                    recommended_fix=(
                        "Generate a unique event_id (e.g. order_id or UUID) on page load and pass the exact same "
                        "value to both fbq('track', 'Purchase', ..., {eventID: id}) and server CAPI payload."
                    ),
                    occurrence_count=missing_client_event_id,
                    sample_payload={"missing_event_id_count": missing_client_event_id},
                )
            )

        # 2. Server EMQ (Event Match Quality) score
        emq_score = 0.0
        if server_events:
            total_server = len(server_events)
            has_email = sum(1 for e in server_events if e.hashed_email and len(e.hashed_email) == 64)
            has_phone = sum(1 for e in server_events if e.hashed_phone and len(e.hashed_phone) == 64)
            has_source = sum(1 for e in server_events if e.action_source == "website")

            # Score out of 10.0
            email_pts = (has_email / total_server) * 5.0
            phone_pts = (has_phone / total_server) * 3.0
            source_pts = (has_source / total_server) * 2.0
            emq_score = round(email_pts + phone_pts + source_pts, 1)

            if emq_score < 6.0:
                findings.append(
                    DiagnosticFinding(
                        id="capi-low-emq-score",
                        category=IssueCategory.CLIENT_SERVER_DISCREPANCY,
                        severity=Severity.HIGH,
                        title=f"Suboptimal Meta CAPI Event Match Quality (EMQ Score: {emq_score}/10)",
                        description=(
                            f"Server CAPI events achieve an EMQ score of only {emq_score}/10. "
                            f"Email coverage: {(has_email/total_server)*100:.1f}%, "
                            f"Phone coverage: {(has_phone/total_server)*100:.1f}%."
                        ),
                        entity_type="event_match_quality",
                        entity_value=f"score={emq_score}",
                        impact="Low match rates hinder ad platform attribution and limit lookalike audience accuracy.",
                        recommended_fix="Send normalized SHA-256 hashed email, phone, city, state, zip, and external_id in server CAPI user_data.",
                        occurrence_count=total_server,
                        sample_payload={"emq_score": emq_score, "has_email": has_email, "has_phone": has_phone},
                    )
                )

        # 3. Ad-blocker & iOS client drop-off analysis
        server_order_ids = {e.order_id or e.event_id for e in server_purchases if (e.order_id or e.event_id)}
        client_order_ids = {e.transaction_id or e.event_id for e in client_purchases if (e.transaction_id or e.event_id)}

        ad_blocker_dropoff_pct = 0.0
        if server_order_ids:
            missed_by_client = server_order_ids - client_order_ids
            ad_blocker_dropoff_pct = round((len(missed_by_client) / len(server_order_ids)) * 100, 1)

            if ad_blocker_dropoff_pct > 10.0:
                findings.append(
                    DiagnosticFinding(
                        id="capi-client-signal-loss",
                        category=IssueCategory.CLIENT_SERVER_DISCREPANCY,
                        severity=Severity.MEDIUM,
                        title=f"Browser Signal Loss Detected ({ad_blocker_dropoff_pct}% Ad-Blocker / ITP Drop-off)",
                        description=(
                            f"{len(missed_by_client)} server-recorded orders were never captured by browser client tags. "
                            f"Signal loss rate: {ad_blocker_dropoff_pct}%."
                        ),
                        entity_type="signal_loss_rate",
                        entity_value=f"{ad_blocker_dropoff_pct}%",
                        impact=(
                            "Relying solely on client tags underreports ROAS and fails to feed conversion signals to smart bidding."
                        ),
                        recommended_fix="Implement robust Server-Side CAPI (Cloud GTM / direct server webhook) to recover blocked conversions.",
                        occurrence_count=len(missed_by_client),
                        sample_payload={
                            "server_orders_count": len(server_order_ids),
                            "client_orders_count": len(client_order_ids),
                            "missed_by_client_count": len(missed_by_client),
                            "signal_loss_pct": ad_blocker_dropoff_pct,
                        },
                    )
                )

        # Calculate estimated overcounting percentage from client side duplicate transactions
        client_txn_counts: dict[str, int] = {}
        for cp in client_purchases:
            if cp.transaction_id:
                client_txn_counts[cp.transaction_id] = client_txn_counts.get(cp.transaction_id, 0) + 1

        total_txns = len(client_purchases)
        duplicates = sum(count - 1 for count in client_txn_counts.values() if count > 1)
        overcounting_pct = round((duplicates / total_txns) * 100, 1) if total_txns > 0 else 0.0

        return findings, overcounting_pct, emq_score, ad_blocker_dropoff_pct
