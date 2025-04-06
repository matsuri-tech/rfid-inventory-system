# app/utils/logging_utils.py

from google.cloud import bigquery
from datetime import datetime
from typing import List, Dict

def log_skipped_rows(logs: List[Dict], log_type: str, table: str = "m2m-core.zzz_logistics.log_skipped_rfid"):
    """
    共通スキップログ出力関数

    Args:
        logs (List[Dict]): スキップ対象のログデータ
        log_type (str): 工程名（例: 'receiving', 'picking'）
        table (str): BigQueryのスキップログテーブル名
    """
    if not logs:
        return

    enriched_logs = []
    now = datetime.utcnow().isoformat()

    for row in logs:
        enriched_logs.append({
            "log_id": row.get("log_id"),
            "rfid_id": row.get("rfid_id"),
            "log_type": log_type,
            "reason": row.get("reason", "unspecified"),
            "received_at": row.get("received_at"),
            "logged_at": now
        })

    client = bigquery.Client()
    client.insert_rows_json(table, enriched_logs)
