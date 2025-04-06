from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/receiving/small-rfid")
async def receive_small_rfid(request: Request):
    data = await request.json()
    log_id = data.get("log_id")

    if not log_id:
        return {"error": "Missing log_id"}, 400

    client = bigquery.Client()

    # ① tempテーブルからデータ取得
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
    rfid_list_str = row.get("rfid_list")
    if not rfid_list_str:
        return {"status": "skipped", "reason": "No rfid_list in temp record"}

    # カンマで分割して1つずつ処理
    rfid_ids = [r.strip() for r in rfid_list_str.split(",") if r.strip()]
    if not rfid_ids:
        return {"status": "skipped", "reason": "Empty rfid list after split"}

    jst_time = (datetime.utcnow() + timedelta(hours=9)).isoformat()

    # ② 本テーブルに挿入する行を構築
    insert_rows = []
    for rfid in rfid_ids:
        insert_rows.append({
            "log_id": log_id,
            "rfid_id": rfid,
            "warehouse_name": row.get("warehouse_name"),
            "listing_id": row.get("listing_id"),
            "source": "AppSheet",
            "received_at": jst_time,
            "processed": False
        })

    # ③ 本テーブルへINSERT
    target_table = "m2m-core.zzz_logistics.log_receiving_small_rfid"
    errors = client.insert_rows_json(target_table, insert_rows)
    if errors:
        return {"error": "Insert failed", "details": errors}, 500

    # ④ processed = TRUE に更新
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

