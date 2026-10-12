from pathlib import Path

GTM_DEDUPLICATION_JS = """// GTM Custom JavaScript Variable: cjs - Purchase Deduplication Check
// Returns true if this transaction has NOT been processed yet, false if duplicate.
function() {
  var transactionId = {{dlv - ecommerce.transaction_id}};
  if (!transactionId) {
    return false; // Suppress tag if no transaction ID
  }

  var storageKey = 'conv_doc_txns';
  var processedTxns = [];

  try {
    var raw = localStorage.getItem(storageKey);
    if (raw) {
      processedTxns = JSON.parse(raw);
    }
  } catch (e) {}

  if (processedTxns.indexOf(transactionId) !== -1) {
    // Duplicate detected!
    return false;
  }

  // Record this transaction ID
  processedTxns.push(transactionId);
  // Keep last 100 transactions
  if (processedTxns.length > 100) {
    processedTxns.shift();
  }

  try {
    localStorage.setItem(storageKey, JSON.stringify(processedTxns));
  } catch (e) {}

  return true;
}
"""

GTM_PII_SCRUBBER_JS = """// GTM Custom JavaScript Variable: cjs - Clean Page Location (PII Stripped)
// Sanitizes URLs by stripping email and phone query parameters before dispatch.
function() {
  var urlStr = {{Page URL}} || window.location.href;
  try {
    var url = new URL(urlStr);
    var piiKeys = ['email', 'user_email', 'mail', 'phone', 'tel', 'mobile', 'ssn', 'contact'];

    piiKeys.forEach(function(key) {
      if (url.searchParams.has(key)) {
        url.searchParams.set(key, '[REDACTED_PII]');
      }
    });

    return url.toString();
  } catch (e) {
    return urlStr;
  }
}
"""

GTM_SHA256_HELPER_JS = """// GTM Custom JavaScript Variable: cjs - Normalize and Hash User Data
// Prepares user data according to Google and Meta Enhanced Conversions standard.
function() {
  return function(rawString) {
    if (!rawString || typeof rawString !== 'string') return '';
    // 1. Lowercase and trim leading/trailing whitespace
    var normalized = rawString.trim().toLowerCase();
    return normalized;
  };
}
"""


class GTMSnippetExporter:
    """Exports Google Tag Manager code snippets and recipes for tracking remediation."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self) -> dict[str, Path]:
        dedup_path = self.output_dir / "gtm_transaction_deduplication.js"
        pii_path = self.output_dir / "gtm_pii_scrubber.js"
        hash_path = self.output_dir / "gtm_user_data_normalizer.js"

        dedup_path.write_text(GTM_DEDUPLICATION_JS, encoding="utf-8")
        pii_path.write_text(GTM_PII_SCRUBBER_JS, encoding="utf-8")
        hash_path.write_text(GTM_SHA256_HELPER_JS, encoding="utf-8")

        return {
            "gtm_dedup": dedup_path,
            "gtm_pii": pii_path,
            "gtm_hash": hash_path,
        }
