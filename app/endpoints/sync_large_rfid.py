from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime
import ulid

router = APIRouter()

@router.post("/sync/large-rfid")
async def sync_large_rfid(request: Request):
    data = await request.json()
    hardware_key = data.get("hardwareKey")

    if not hardware_key:
        return {"error": "Missing hardwareKey"}, 400

    client = bigquery.Client()

    # Step1: 対象データの抽出（UNIQUEなEPC）
    query = f"""
        SELECT AS STRUCT *
        FROM (
            SELECT *,
              ROW_NUMBER() OVER(PARTITION BY epc ORDER BY read_timestamp DESC) AS rn
            FROM `m2m-core.zzz_logistics.t_temp_receiving_large_rfid`
            WHERE processed = FALSE AND hardwareKey = @hardwareKey
        )
        WHERE rn = 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("hardwareKey", "STRING", hardware_key)
        ]
    )
    query_job = client.query(query, job_config=job_config)
    rows = [dict(row) for row in query_job]

    if not rows:
        return {"status": "no unprocessed rows found"}, 200

    # Step2: logテーブルにINSERT用データを整形
    insert_rows = []
    for row in rows:
        read_ts = row.get("read_timestamp")
        insert_rows.append({
            "id": row.get("id"),
            "read_timestamp": read_ts.isoformat() if isinstance(read_ts, datetime) else read_ts,
            "hardwareKey": row.get("hardwareKey"),
            "commandCode": row.get("commandCode"),
            "tagRecNums": row.get("tagRecNums"),
            "epc": row.get("epc"),
            "antNo": row.get("antNo"),
            "len": row.get("len"),
            "processed": True
        })

    # Step3: 本テーブルへInsert
    log_table_id = "m2m-core.zzz_logistics.log_receiving_large_rfid"
    errors = client.insert_rows_json(log_table_id, insert_rows)
    if errors:
        return {"error": "Insert failed", "details": errors}, 500

    # Step4: tempテーブル側のprocessedをTRUEに更新
    ids = [f'"{row["id"]}"' for row in rows]
    update_query = f"""
        UPDATE `m2m-core.zzz_logistics.t_temp_receiving_large_rfid`
        SET processed = TRUE
        WHERE id IN ({','.join(ids)})
    """
    client.query(update_query).result()

    return {"status": "ok", "synced": len(rows)}
