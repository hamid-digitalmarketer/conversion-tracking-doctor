from typing import List

from conversion_tracking_doctor.models import (
    ClientEventRow,
    DiagnosticFinding,
    IssueCategory,
    Severity,
)

STANDARD_GA4_ECOMMERCE_EVENTS = {
    "view_item_list",
    "select_item",
    "view_item",
    "add_to_cart",
    "remove_from_cart",
    "view_cart",
    "begin_checkout",
    "add_shipping_info",
    "add_payment_info",
    "purchase",
    "refund",
}

NON_STANDARD_COMMON_NAMES = {
    "buy",
    "buy_now",
    "order_completed",
    "order_complete",
    "checkout_success",
    "thank_you",
    "cart_added",
    "item_viewed",
}


class EcommerceSchemaAnalyzer:
    """Validates adherence to GA4 and Meta standard e-commerce event schemas and naming."""

    def analyze(self, events: List[ClientEventRow]) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        missing_txn_purchases = 0
        missing_items_purchases = 0
        non_standard_event_counts: dict[str, int] = {}

        for event in events:
            ev_name = event.event_name.lower().strip()

            if ev_name in NON_STANDARD_COMMON_NAMES:
                non_standard_event_counts[ev_name] = non_standard_event_counts.get(ev_name, 0) + 1

            if ev_name in ("purchase", "ecommerce_purchase"):
                if not event.transaction_id or not event.transaction_id.strip():
                    missing_txn_purchases += 1
                if event.items_count is None or event.items_count <= 0:
                    missing_items_purchases += 1

        if missing_txn_purchases > 0:
            findings.append(
                DiagnosticFinding(
                    id="schema-missing-transaction-id",
                    category=IssueCategory.MISSING_ECOMMERCE_SCHEMA,
                    severity=Severity.CRITICAL,
                    title=f"Missing transaction_id on {missing_txn_purchases} Purchase Events",
                    description=(
                        f"Detected {missing_txn_purchases} purchase events without a transaction_id. "
                        "Without an order identifier, conversion deduplication is completely disabled."
                    ),
                    entity_type="ecommerce_schema_parameter",
                    entity_value="transaction_id=None",
                    impact="Severe risk of unlimited multi-counting on page refreshes and inability to audit against CRM revenue.",
                    recommended_fix="Populate transaction_id from your e-commerce order confirmation payload.",
                    occurrence_count=missing_txn_purchases,
                    sample_payload={"missing_transaction_id_count": missing_txn_purchases},
                )
            )

        if missing_items_purchases > 0:
            findings.append(
                DiagnosticFinding(
                    id="schema-missing-items-array",
                    category=IssueCategory.MISSING_ECOMMERCE_SCHEMA,
                    severity=Severity.HIGH,
                    title=f"Missing or Empty items Array on {missing_items_purchases} Purchase Events",
                    description=(
                        f"Detected {missing_items_purchases} purchase events where items array has 0 items or is missing. "
                        "GA4 requires the items array for item-scoped metrics, gross revenue, and product conversion rates."
                    ),
                    entity_type="ecommerce_schema_parameter",
                    entity_value="items=[]",
                    impact="Item-scoped e-commerce reports (item revenue, item purchase quantity) will show zero data in GA4.",
                    recommended_fix="Include items array containing item_id, item_name, price, and quantity.",
                    occurrence_count=missing_items_purchases,
                    sample_payload={"missing_items_count": missing_items_purchases},
                )
            )

        for non_std_name, count in non_standard_event_counts.items():
            findings.append(
                DiagnosticFinding(
                    id=f"schema-non-standard-{non_std_name}",
                    category=IssueCategory.MISSING_ECOMMERCE_SCHEMA,
                    severity=Severity.MEDIUM,
                    title=f"Non-Standard E-Commerce Event Name: '{non_std_name}'",
                    description=(
                        f"Custom event name '{non_std_name}' fired {count} times instead of standard GA4 / Meta naming convention. "
                        "Standard reporting widgets and funnel visualizers only recognize standard names."
                    ),
                    entity_type="event_name",
                    entity_value=non_std_name,
                    impact="Breaks built-in GA4 monetization funnel reports and automated conversion actions in Google Ads.",
                    recommended_fix=f"Rename event from '{non_std_name}' to standard equivalent (e.g. 'purchase' or 'add_to_cart').",
                    occurrence_count=count,
                    sample_payload={"event_name": non_std_name, "count": count},
                )
            )

        return findings
