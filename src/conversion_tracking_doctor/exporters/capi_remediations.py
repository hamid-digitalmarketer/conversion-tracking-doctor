from pathlib import Path

PYTHON_CAPI_TEMPLATE = """# Python Meta Conversions API (CAPI) Remediation Template
import hashlib
import time
import requests

def sha256_normalize(value: str) -> str:
    \"\"\"Normalizes and computes lowercase SHA-256 hash.\"\"\"
    if not value:
        return ""
    cleaned = value.strip().lower()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

def send_meta_capi_purchase(
    pixel_id: str,
    access_token: str,
    event_id: str,  # MUST match the client browser eventID
    order_id: str,
    value: float,
    currency: str,
    email: str,
    phone: str,
    event_source_url: str,
):
    url = f"https://graph.facebook.com/v19.0/{pixel_id}/events"
    payload = {
        "data": [
            {
                "event_name": "Purchase",
                "event_time": int(time.time()),
                "event_id": event_id,
                "event_source_url": event_source_url,
                "action_source": "website",
                "user_data": {
                    "em": [sha256_normalize(email)],
                    "ph": [sha256_normalize(phone)] if phone else [],
                },
                "custom_data": {
                    "currency": currency.upper(),
                    "value": round(float(value), 2),
                    "order_id": order_id,
                },
            }
        ],
        "access_token": access_token,
    }
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()
"""

NODEJS_CAPI_TEMPLATE = """// Node.js Meta CAPI Remediation Snippet
const crypto = require('crypto');

function sha256Normalize(str) {
  if (!str) return '';
  return crypto.createHash('sha256').update(str.trim().toLowerCase()).digest('hex');
}

function buildCapiPurchasePayload({
  eventId, // EXACT MATCH to browser fbq('track', 'Purchase', ..., { eventID: eventId })
  orderId,
  value,
  currency,
  email,
  phone,
  sourceUrl
}) {
  return {
    data: [
      {
        event_name: 'Purchase',
        event_time: Math.floor(Date.now() / 1000),
        event_id: eventId,
        event_source_url: sourceUrl,
        action_source: 'website',
        user_data: {
          em: [sha256Normalize(email)],
          ph: phone ? [sha256Normalize(phone)] : []
        },
        custom_data: {
          currency: currency.toUpperCase(),
          value: parseFloat(value.toFixed(2)),
          order_id: orderId
        }
      }
    ]
  };
}

module.exports = { sha256Normalize, buildCapiPurchasePayload };
"""


class CAPIRemediationExporter:
    """Exports server-side CAPI code snippets and payload recipes."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self) -> dict[str, Path]:
        py_path = self.output_dir / "meta_capi_remediation.py"
        js_path = self.output_dir / "meta_capi_remediation.js"

        py_path.write_text(PYTHON_CAPI_TEMPLATE, encoding="utf-8")
        js_path.write_text(NODEJS_CAPI_TEMPLATE, encoding="utf-8")

        return {
            "capi_python": py_path,
            "capi_node": js_path,
        }
