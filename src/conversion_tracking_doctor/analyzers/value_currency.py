from typing import List

from conversion_tracking_doctor.models import (
    ClientEventRow,
    DiagnosticFinding,
    IssueCategory,
    Severity,
)

STANDARD_CURRENCIES = {
    "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY", "INR", "CHF", "NZD",
    "SGD", "HKD", "SEK", "NOK", "DKK", "PLN", "MXN", "BRL", "ZAR", "AED", "SAR"
}


class ValueCurrencyAnalyzer:
    """Detects invalid currency codes, missing currencies, zero values, and decimal scaling errors."""

    def analyze(self, events: List[ClientEventRow]) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        zero_value_purchases: List[ClientEventRow] = []
        invalid_currency_purchases: List[ClientEventRow] = []
        scale_error_purchases: List[ClientEventRow] = []

        purchase_values: List[float] = [
            e.value for e in events
            if e.event_name.lower() in ("purchase", "ecommerce_purchase") and e.value is not None and e.value > 0
        ]
        median_value = (
            sorted(purchase_values)[len(purchase_values) // 2] if purchase_values else 100.0
        )

        for event in events:
            if event.event_name.lower() in ("purchase", "ecommerce_purchase"):
                val = event.value
                curr = (event.currency or "").strip().upper()

                # Check currency
                if not curr or curr not in STANDARD_CURRENCIES:
                    invalid_currency_purchases.append(event)

                # Check value
                if val is None or val <= 0:
                    zero_value_purchases.append(event)
                elif val > (median_value * 50) and val > 5000.0:
                    # Likely cents passed as whole currency (e.g., $150.00 passed as 15000.00)
                    scale_error_purchases.append(event)

        if zero_value_purchases:
            findings.append(
                DiagnosticFinding(
                    id="val-zero-value-purchases",
                    category=IssueCategory.VALUE_CURRENCY_ANOMALY,
                    severity=Severity.HIGH,
                    title=f"Zero or Missing Revenue Value on {len(zero_value_purchases)} Purchase Events",
                    description=(
                        f"Detected {len(zero_value_purchases)} purchase events with value=0 or value=None. "
                        "Ad platforms cannot compute Target ROAS or Value-based bidding without monetary values."
                    ),
                    entity_type="event_parameter",
                    entity_value="value=0",
                    impact="Degrades automated smart bidding. ROAS reporting shows $0.00 even when transactions occur.",
                    recommended_fix="Verify that dataLayer.ecommerce.value is populated and cast as a numeric float.",
                    occurrence_count=len(zero_value_purchases),
                    sample_payload={
                        "zero_value_events_count": len(zero_value_purchases),
                        "sample_transaction_ids": [e.transaction_id for e in zero_value_purchases[:5] if e.transaction_id],
                    },
                )
            )

        if invalid_currency_purchases:
            sample_currencies = list({e.currency or "(empty)" for e in invalid_currency_purchases[:5]})
            findings.append(
                DiagnosticFinding(
                    id="curr-invalid-iso-code",
                    category=IssueCategory.VALUE_CURRENCY_ANOMALY,
                    severity=Severity.HIGH,
                    title="Invalid or Missing ISO 4217 Currency Code",
                    description=(
                        f"{len(invalid_currency_purchases)} events sent non-standard currency values: {sample_currencies}. "
                        "Platforms require 3-letter uppercase ISO 4217 codes (e.g. USD, EUR, GBP)."
                    ),
                    entity_type="currency_parameter",
                    entity_value=str(sample_currencies),
                    impact="Ad platforms drop conversion values or apply incorrect default currency conversion rates.",
                    recommended_fix="Ensure GTM currency variable returns standard ISO 4217 uppercase code (e.g. 'USD').",
                    occurrence_count=len(invalid_currency_purchases),
                    sample_payload={
                        "invalid_currencies": sample_currencies,
                        "occurrence_count": len(invalid_currency_purchases),
                    },
                )
            )

        if scale_error_purchases:
            findings.append(
                DiagnosticFinding(
                    id="val-cents-scale-anomaly",
                    category=IssueCategory.VALUE_CURRENCY_ANOMALY,
                    severity=Severity.CRITICAL,
                    title="Extreme Revenue Scale Error (Cents Passed as Whole Currency)",
                    description=(
                        f"Detected {len(scale_error_purchases)} purchase events with values over 50x median ($>5,000). "
                        "Typical cause: passing raw Stripe/Shopify integer cents (e.g. 19999) without dividing by 100."
                    ),
                    entity_type="event_value_scaling",
                    entity_value="100x_multiplier",
                    impact="Corrupts target ROAS bidding models, resulting in hyper-aggressive runaway bids on false high-value signals.",
                    recommended_fix="Divide checkout amount by 100 before pushing to dataLayer (amount / 100.0).",
                    occurrence_count=len(scale_error_purchases),
                    sample_payload={
                        "scale_error_count": len(scale_error_purchases),
                        "sample_values": [e.value for e in scale_error_purchases[:3]],
                    },
                )
            )

        return findings
