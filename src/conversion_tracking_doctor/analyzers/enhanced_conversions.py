import re
from typing import List

from conversion_tracking_doctor.models import (
    ClientEventRow,
    DiagnosticFinding,
    IssueCategory,
    Severity,
)

HEX_64_REGEX = re.compile(r"^[a-f0-9]{64}$")
UPPER_HEX_REGEX = re.compile(r"^[A-Fa-f0-9]{64}$")


class EnhancedConversionsAnalyzer:
    """Validates user data hashing and formatting for Google Ads Enhanced Conversions and Meta Advanced Matching."""

    def analyze(self, events: List[ClientEventRow]) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        unhashed_user_data_count = 0
        improper_hash_format_count = 0
        total_purchases = 0
        missing_user_data_purchases = 0

        for event in events:
            if event.event_name.lower() in ("purchase", "generate_lead", "sign_up"):
                total_purchases += 1
                email = event.user_data_email
                phone = event.user_data_phone

                if not email and not phone:
                    missing_user_data_purchases += 1
                    continue

                if email:
                    # Check if it's plaintext email instead of sha256
                    if "@" in email:
                        unhashed_user_data_count += 1
                    elif UPPER_HEX_REGEX.match(email) and not HEX_64_REGEX.match(email):
                        # Contains uppercase letters
                        improper_hash_format_count += 1
                    elif not HEX_64_REGEX.match(email):
                        improper_hash_format_count += 1

                if phone:
                    if not HEX_64_REGEX.match(phone):
                        if any(c.isdigit() for c in phone):
                            unhashed_user_data_count += 1
                        else:
                            improper_hash_format_count += 1

        if unhashed_user_data_count > 0:
            findings.append(
                DiagnosticFinding(
                    id="ec-unhashed-user-data",
                    category=IssueCategory.BROKEN_ENHANCED_CONVERSIONS,
                    severity=Severity.CRITICAL,
                    title="Unhashed Plaintext User Data in Enhanced Conversions Payload",
                    description=(
                        f"Detected {unhashed_user_data_count} conversion events sending raw, unhashed email or phone "
                        "parameters to conversion endpoints."
                    ),
                    entity_type="enhanced_conversions_payload",
                    entity_value="raw_user_data",
                    impact=(
                        "Google Ads and Meta reject unhashed user data via client endpoints. Severe privacy compliance violation."
                    ),
                    recommended_fix=(
                        "Ensure email is lowercased, trimmed of leading/trailing whitespace, and SHA-256 hashed "
                        "before assigning to user_data.email."
                    ),
                    occurrence_count=unhashed_user_data_count,
                    sample_payload={"unhashed_events_detected": unhashed_user_data_count},
                )
            )

        if improper_hash_format_count > 0:
            findings.append(
                DiagnosticFinding(
                    id="ec-malformed-hash",
                    category=IssueCategory.BROKEN_ENHANCED_CONVERSIONS,
                    severity=Severity.HIGH,
                    title="Malformed SHA-256 Hash Formatting (Uppercase or Invalid Length)",
                    description=(
                        f"Detected {improper_hash_format_count} hashed parameters with uppercase hex characters or invalid lengths. "
                        "Ad platforms require strict lowercase 64-character hexadecimal SHA-256 strings."
                    ),
                    entity_type="enhanced_conversions_hash",
                    entity_value="malformed_sha256",
                    impact="Ad platforms fail to match hashes against user accounts, resulting in 0% match rate boost.",
                    recommended_fix="Apply .toLowerCase().trim() in JavaScript prior to hashing: crypto.subtle.digest('SHA-256', ...).",
                    occurrence_count=improper_hash_format_count,
                    sample_payload={"malformed_hashes_count": improper_hash_format_count},
                )
            )

        if total_purchases > 0 and (missing_user_data_purchases / total_purchases) > 0.4:
            pct_missing = (missing_user_data_purchases / total_purchases) * 100
            findings.append(
                DiagnosticFinding(
                    id="ec-missing-enhanced-conversions",
                    category=IssueCategory.BROKEN_ENHANCED_CONVERSIONS,
                    severity=Severity.MEDIUM,
                    title="High Rate of Missing User Data on Purchase Events",
                    description=(
                        f"{missing_user_data_purchases} of {total_purchases} ({pct_missing:.1f}%) conversion events lack "
                        "Enhanced Conversion user data (email/phone match keys)."
                    ),
                    entity_type="enhanced_conversions_adoption",
                    entity_value="missing_match_keys",
                    impact="Loss of 15-30% attributable conversions on Safari, Firefox, and iOS devices with third-party cookie blocking.",
                    recommended_fix="Configure GTM User-Provided Data variable pulling email from the checkout dataLayer.",
                    occurrence_count=missing_user_data_purchases,
                    sample_payload={
                        "missing_count": missing_user_data_purchases,
                        "total_purchases": total_purchases,
                        "missing_percentage": round(pct_missing, 1),
                    },
                )
            )

        return findings
