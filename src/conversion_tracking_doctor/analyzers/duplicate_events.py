from collections import defaultdict
from typing import List

from conversion_tracking_doctor.models import (
    ClientEventRow,
    DiagnosticFinding,
    IssueCategory,
    Severity,
)


class DuplicateEventsAnalyzer:
    """Detects duplicate transaction IDs and re-firing purchase events."""

    def analyze(self, events: List[ClientEventRow]) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        purchases_by_txn: dict[str, List[ClientEventRow]] = defaultdict(list)

        for event in events:
            if event.event_name.lower() in ("purchase", "ecommerce_purchase") and event.transaction_id:
                purchases_by_txn[event.transaction_id].append(event)

        for txn_id, event_list in purchases_by_txn.items():
            if len(event_list) > 1:
                total_value = sum(e.value or 0.0 for e in event_list)
                duplicate_cost = sum(e.value or 0.0 for e in event_list[1:])
                duplicate_count = len(event_list) - 1

                findings.append(
                    DiagnosticFinding(
                        id=f"dup-txn-{txn_id}",
                        category=IssueCategory.DUPLICATE_EVENT,
                        severity=Severity.CRITICAL,
                        title=f"Duplicate Purchase Event: Order #{txn_id} fired {len(event_list)} times",
                        description=(
                            f"Transaction ID '{txn_id}' fired {len(event_list)} times across client sessions. "
                            f"This indicates order confirmation / thank-you page reloading without deduplication logic."
                        ),
                        entity_type="transaction_id",
                        entity_value=txn_id,
                        impact=(
                            f"Overcounts revenue by ${duplicate_cost:,.2f} ({duplicate_count} phantom conversions). "
                            "Artificially inflates reported ROAS and misleads smart bidding algorithms."
                        ),
                        recommended_fix=(
                            "Implement GTM 1st-party cookie or localStorage transaction deduplication check, "
                            "or generate a unique event_id and ensure server-side deduplication."
                        ),
                        occurrence_count=len(event_list),
                        sample_payload={
                            "transaction_id": txn_id,
                            "occurrences": len(event_list),
                            "total_reported_value": total_value,
                            "phantom_value": duplicate_cost,
                            "timestamps": [e.timestamp for e in event_list],
                        },
                    )
                )

        return findings
