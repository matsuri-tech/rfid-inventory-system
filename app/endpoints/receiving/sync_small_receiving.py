# app/endpoints/receiving/sync_small_receiving.py

from fastapi import APIRouter
from google.cloud import bigquery
from datetime import datetime, timedelta
import ulid

router = APIRouter()

@router.post("/receiving/sync-small-rfid")
async def sync_small_receiving():
    client = bigquery.Client()

    temp_table = "m2m-core.zzz_logistics.t_temp_receiving_small_rfid"
    target_table = "m2m-core.zzz_logistics.log_receiving_small_rfid"

    # Step 1: 未処理のデータ取得
    query = f"""
        SELECT *
        FROM `{temp_table}`
        WHERE processed = FALSE
        LIMIT 10
    """
    rows = list(client.query(query).result())

    if not rows:
        return {"status": "skipped", "reason": "no unprocessed rows"}

    results = []
    for row in rows:
        log_id = row.get("log_id") or f"log_{ulid.new().str.lower()}"
        rfid_list_str = row.get("rfid_list")
        warehouse_name = row.get("warehouse_name")
        listing_id = row.get("listing_id")

        if not rfid_list_str:
            continue

        rfid_list = [r.strip() for r in rfid_list_str.split(",") if r.strip()]
        if not rfid_list:
            continue

        now_jst = (datetime.utcnow() + timedelta(hours=9)).isoformat()

        insert_rows = []
        for rfid in rfid_list:
            insert_rows.append({
                "log_id": log_id,
                "rfid_id": rfid,
                "warehouse_name": warehouse_name,
                "listing_id": listing_id,
                "source": "AppSheet",
                "received_at": now_jst,
                "processed": False
            })

        # Step 2: 本テーブルにINSERT
        errors = client.insert_rows_json(target_table, insert_rows)
        if errors:
            return {"status": "error", "stage": "insert", "details": errors}, 500

        # Step 3: tempテーブルの processed を TRUE に更新
        update_query = f"""
            UPDATE `{temp_table}`
            SET processed = TRUE
            WHERE log_id = @log_id
        """
        client.query(update_query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("log_id", "STRING", row["log_id"])
            ]
        )).result()

        results.append({
            "log_id": row["log_id"],
            "inserted": len(insert_rows)
        })

    return {"status": "success", "results": results}
