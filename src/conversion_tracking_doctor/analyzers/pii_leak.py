import re
from typing import List

from conversion_tracking_doctor.models import (
    ClientEventRow,
    DiagnosticFinding,
    IssueCategory,
    Severity,
)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:\+?1[-. ]?)?\(?[2-9]\d{2}\)?[-. ]?\d{3}[-. ]?\d{4}")


class PIILeakAnalyzer:
    """Scans URLs, query parameters, and custom dimensions for unhashed plaintext PII."""

    def analyze(self, events: List[ClientEventRow]) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        leaked_emails: dict[str, int] = {}
        leaked_phones: dict[str, int] = {}

        for event in events:
            text_targets = [
                event.page_location or "",
                event.custom_parameters or "",
            ]

            for text in text_targets:
                if not text:
                    continue

                for email_match in EMAIL_REGEX.finditer(text):
                    email = email_match.group(0).lower()
                    leaked_emails[email] = leaked_emails.get(email, 0) + 1

                for phone_match in PHONE_REGEX.finditer(text):
                    phone = phone_match.group(0)
                    # Filter out short strings or false positives like timestamps
                    if len(re.sub(r"\D", "", phone)) >= 10:
                        leaked_phones[phone] = leaked_phones.get(phone, 0) + 1

        for email, count in leaked_emails.items():
            findings.append(
                DiagnosticFinding(
                    id=f"pii-email-{hash(email) % 1000000:06x}",
                    category=IssueCategory.PII_LEAK,
                    severity=Severity.CRITICAL,
                    title="Plaintext Email Detected in URL / Event Parameters",
                    description=(
                        f"Found plaintext email address '{email[:3]}***@{email.split('@')[-1]}' "
                        f"exposed in URL query parameters or custom event payload across {count} hits."
                    ),
                    entity_type="url_parameter",
                    entity_value=email,
                    impact=(
                        "Direct violation of Google Analytics Terms of Service and Meta Developer Policies. "
                        "Risk of account suspension, GDPR / CCPA regulatory non-compliance, and cross-site privacy leakage."
                    ),
                    recommended_fix=(
                        "Strip query parameters containing user emails (e.g. ?email=, ?contact=) in GTM URL variables "
                        "before sending pageview/event tags to GA4 and Meta Pixel."
                    ),
                    occurrence_count=count,
                    sample_payload={"masked_email": f"{email[:3]}***@{email.split('@')[-1]}", "occurrences": count},
                )
            )

        for phone, count in leaked_phones.items():
            findings.append(
                DiagnosticFinding(
                    id=f"pii-phone-{hash(phone) % 1000000:06x}",
                    category=IssueCategory.PII_LEAK,
                    severity=Severity.CRITICAL,
                    title="Plaintext Phone Number Detected in URL / Parameters",
                    description=f"Plaintext phone number '{phone[:4]}***' detected in event payload across {count} hits.",
                    entity_type="url_parameter",
                    entity_value=phone,
                    impact="Violates platform privacy policies. Can lead to immediate advertising account restrictions.",
                    recommended_fix="Sanitize form redirect URLs to prevent passing sensitive user phone numbers in GET parameters.",
                    occurrence_count=count,
                    sample_payload={"masked_phone": f"{phone[:4]}***", "occurrences": count},
                )
            )

        return findings
