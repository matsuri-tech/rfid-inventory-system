from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime, timedelta
import ulid

router = APIRouter()

@router.post("/receiving/small-rfid")
async def receive_small_rfid(request: Request):
    data = await request.json()
    log_id = data.get("log_id")

    if not log_id:
        return {"error": "Missing log_id"}, 400

    client = bigquery.Client()

    # ① 一時テーブルから log_id に一致する行を取得
    temp_table = "m2m-core.zzz_logistics.t_temp_receiving_small_rfid"
    query = f"""
        SELECT * FROM `{temp_table}`
        WHERE log_id = @log_id AND processed = FALSE
    """
    job = client.query(query, job_config=bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("log_id", "STRING", log_id)
        ]
    ))

    results = list(job.result())
    if not results:
        return {"status": "skipped", "reason": "Already processed or not found"}

    row = results[0]
    rfid_str = row["rfid_id"]
    rfid_list = [r.strip() for r in rfid_str.split("\n") if r.strip()]

    # JST timestamp
    jst_time = (datetime.utcnow() + timedelta(hours=9)).isoformat()

    # ② 新しい行を作成して本番テーブルへ INSERT
    insert_rows = []
    for rfid in rfid_list:
        insert_rows.append({
            "log_id": log_id,
            "rfid_id": rfid,
            "warehouse_name": row["warehouse_name"],
            "listing_id": row["listing_id"],
            "source": "AppSheet",
            "received_at": jst_time,
            "processed": False
        })

    target_table = "m2m-core.zzz_logistics.log_receiving_small_rfid"
    insert_errors = client.insert_rows_json(target_table, insert_rows)
    if insert_errors:
        return {"error": "Insert failed", "details": insert_errors}, 500

    # ③ processed = TRUE に更新
    update_query = f"""
        UPDATE `{temp_table}`
        SET processed = TRUE
        WHERE log_id = @log_id
    """
    client.query(update_query, job_config=bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("log_id", "STRING", log_id)
        ]
    )).result()

    return {"status": "success", "inserted": len(insert_rows)}
