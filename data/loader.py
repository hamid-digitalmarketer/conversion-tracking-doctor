import csv
from pathlib import Path
from typing import List, Optional

from conversion_tracking_doctor.models import ClientEventRow, ServerCAPIEventRow


def _parse_float(val: Optional[str]) -> Optional[float]:
    if not val or val.strip() == "":
        return None
    try:
        return float(val.strip().replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _parse_int(val: Optional[str]) -> Optional[int]:
    if not val or val.strip() == "":
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


def load_client_events(csv_path: Path | str) -> List[ClientEventRow]:
    path = Path(csv_path)
    rows: List[ClientEventRow] = []
    with open(path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                ClientEventRow(
                    event_id=r.get("event_id") or None,
                    event_name=r.get("event_name", "").strip(),
                    timestamp=r.get("timestamp", "").strip(),
                    transaction_id=r.get("transaction_id") or None,
                    value=_parse_float(r.get("value")),
                    currency=r.get("currency") or None,
                    page_location=r.get("page_location") or None,
                    user_data_email=r.get("user_data_email") or None,
                    user_data_phone=r.get("user_data_phone") or None,
                    items_count=_parse_int(r.get("items_count")),
                    custom_parameters=r.get("custom_parameters") or None,
                )
            )
    return rows


def load_server_events(csv_path: Path | str) -> List[ServerCAPIEventRow]:
    path = Path(csv_path)
    rows: List[ServerCAPIEventRow] = []
    with open(path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                ServerCAPIEventRow(
                    event_id=r.get("event_id") or None,
                    event_name=r.get("event_name", "").strip(),
                    timestamp=r.get("timestamp", "").strip(),
                    order_id=r.get("order_id") or None,
                    value=_parse_float(r.get("value")),
                    currency=r.get("currency") or None,
                    hashed_email=r.get("hashed_email") or None,
                    hashed_phone=r.get("hashed_phone") or None,
                    action_source=r.get("action_source") or "website",
                )
            )
    return rows
