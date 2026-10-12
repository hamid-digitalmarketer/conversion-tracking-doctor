# Conversion Tracking Issue Taxonomy & Remediation Guide

This guide details the six core failure modes audited by `conversion-tracking-doctor`, their commercial and regulatory implications, and the industry-standard remediation workflows.

---

## 1. Duplicate Event Firing (`duplicate_event`)
- **Severity**: `CRITICAL`
- **Symptom**: The same `transaction_id` or `order_id` is sent multiple times to GA4, Meta Pixel, or Google Ads.
- **Root Cause**:
  - Customer reloads the order confirmation / thank-you page.
  - Customer navigates away and clicks the browser "Back" button.
  - Confirmation emails linking customers back to the order summary page where tracking tags re-execute.
- **Business Impact**:
  - ROAS is artificially inflated (e.g. 20% to 50%).
  - Smart bidding algorithms (Target CPA / Target ROAS) bid aggressively on non-existent conversion volume, increasing clearing CPCs.
- **Remediation**:
  - Implement localStorage / 1st-party cookie checks to execute tags once per unique transaction ID.
  - Use `reports/gtm_transaction_deduplication.js`.

---

## 2. Personally Identifiable Information (PII) Leaks (`pii_leak`)
- **Severity**: `CRITICAL`
- **Symptom**: Plaintext customer emails (`user@domain.com`) or phone numbers appear in `page_location` query parameters (e.g., `?email=`, `?lead_email=`, `?tel=`) or custom parameters.
- **Root Cause**:
  - Form builders (HubSpot, Typeform, Unbounce) passing lead inputs via GET redirect queries.
  - Email marketing campaigns appending user emails in link click tracking parameters.
- **Business Impact**:
  - Direct breach of Google Analytics Terms of Service and Meta Platform Policy.
  - Potential suspension of ad accounts or revocation of GA4 properties.
  - GDPR, CCPA, and CPRA statutory privacy violations.
- **Remediation**:
  - Strip query parameters containing sensitive keys before firing tags using `reports/gtm_pii_scrubber.js`.
  - Switch lead capture form submissions from GET to POST.

---

## 3. Broken Enhanced Conversions (`broken_enhanced_conversions`)
- **Severity**: `CRITICAL` to `HIGH`
- **Symptom**:
  - Plaintext emails passed directly into Google Ads `user_data` or Meta `em` fields without hashing.
  - Hashes formatted with uppercase hex characters or containing whitespace prior to SHA-256 calculation.
- **Root Cause**:
  - Developer omissions in pre-hashing transformations (`toLowerCase().trim()`).
  - Misconfigured GTM User-Provided Data variables.
- **Business Impact**:
  - Platforms reject the conversion hit or fail to match the user, reducing attribution recovery by 15% to 30%.
- **Remediation**:
  - Standardize hashing pipelines: trim whitespace, convert to lowercase, and hash via SHA-256 (64 hex characters).

---

## 4. Value and Currency Anomalies (`value_currency_anomaly`)
- **Severity**: `CRITICAL` to `HIGH`
- **Symptom**:
  - Purchases recorded with `value=0` or `value=None`.
  - Non-standard currency strings (e.g. `"$"` or `"US DOLLARS"`).
  - Stripe/Shopify integer cents sent as whole currency (e.g., `$299.90` reported as `29990.00`).
- **Root Cause**:
  - Failing to cast dataLayer variables to floating point numbers.
  - Hardcoded currency formatting functions.
- **Business Impact**:
  - 100x value scale spikes distort target ROAS machine learning models.
  - Missing currencies cause conversions to be recorded at 0 monetary value.
- **Remediation**:
  - Divide integer cents by `100.0`.
  - Enforce ISO 4217 uppercase 3-letter codes (`USD`, `EUR`, `GBP`).

---

## 5. Missing Deduplication Keys & Client-Server Discrepancy (`client_server_discrepancy`)
- **Severity**: `CRITICAL` to `MEDIUM`
- **Symptom**:
  - Browser pixel fires without an `event_id`, while server CAPI fires with an `event_id`.
  - Low Event Match Quality (EMQ score < 6.0).
  - High client drop-off rate (> 20%) compared to server-side orders.
- **Root Cause**:
  - Asynchronous tag execution where browser script does not share the same UUID or transaction ID with the backend webhook.
  - Ad-blockers blocking client-side JavaScript libraries (`fbevents.js`, `gtag.js`).
- **Business Impact**:
  - Conversions are counted twice (once by browser, once by server).
  - Loss of 20%+ conversion volume on privacy-centric browsers (Brave, Firefox, Safari iOS).
- **Remediation**:
  - Generate a single `event_id` server-side and pass it to both the client dataLayer and server CAPI payload (`reports/meta_capi_remediation.py`).

---

## 6. Missing Required E-Commerce Schema (`missing_ecommerce_schema`)
- **Severity**: `HIGH` to `MEDIUM`
- **Symptom**:
  - Missing `transaction_id` on purchase events.
  - Empty or missing `items` array.
  - Non-standard event names (e.g., `checkout_success`, `order_complete`).
- **Root Cause**:
  - Legacy Universal Analytics syntax or non-standard custom dataLayer pushes.
- **Business Impact**:
  - Item-level reporting in GA4 shows zero product revenue.
  - GA4 monetization funnel steps appear broken.
- **Remediation**:
  - Migrate to GA4 recommended event syntax (`purchase`, `items: [{item_id, item_name, price, quantity}]`).
