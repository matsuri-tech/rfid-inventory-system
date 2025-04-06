from fastapi import APIRouter
from google.cloud import bigquery
from datetime import datetime
from app.utils.logging_utils import log_skipped_rows  # 共通ログ記録ユーティリティ

router = APIRouter()

@router.post("/picking/update-inventory")
async def update_inventory_from_picking():
    client = bigquery.Client()
    skipped_logs = []

    log_table = "m2m-core.zzz_logistics.log_picking_rfid"
    inventory_table = "m2m-core.zzz_logistics.t_commodity_rfid"
    processed_table = "m2m-core.zzz_logistics.log_processed_status"

    # ✅ 未処理ログ取得（log_idで判定）
    query = f"""
        SELECT log_id, rfid_id, listing_id, warehouse_name, source, received_at
        FROM `{log_table}`
        WHERE processed = FALSE
          AND log_id NOT IN (
              SELECT log_id
              FROM `{processed_table}`
              WHERE log_type = 'picking'
          )
        LIMIT 100
    """
    rows = list(client.query(query).result())
    if not rows:
        return {"status": "skipped", "reason": "no unprocessed logs"}

    valid_rows = []
    for row in rows:
        if not row["rfid_id"] or not row["listing_id"] or not row["warehouse_name"]:
            skipped_logs.append({
                "log_id": row["log_id"],
                "rfid_id": row["rfid_id"],
                "reason": "missing field(s)",
                "received_at": row.get("received_at"),
                "log_type": "picking",
                "logged_at": datetime.utcnow().isoformat()
            })
            continue
        valid_rows.append(row)

    if not valid_rows:
        if skipped_logs:
            log_skipped_rows(skipped_logs, log_type="picking")
        return {"status": "skipped", "reason": "all invalid records", "skipped": len(skipped_logs)}

    # ✅ MERGE 実行
    try:
        merge_query = f"""
            MERGE `{inventory_table}` T
            USING (
                SELECT rfid_id, listing_id, warehouse_name, source, received_at
                FROM `{log_table}`
                WHERE processed = FALSE
                  AND rfid_id IS NOT NULL
                  AND listing_id IS NOT NULL
                  AND warehouse_name IS NOT NULL
                  AND log_id NOT IN (
                      SELECT log_id
                      FROM `{processed_table}`
                      WHERE log_type = 'picking'
                  )
                LIMIT 100
            ) S
            ON T.rfid_id = S.rfid_id
            WHEN MATCHED THEN
              UPDATE SET
                T.status = 'Picking',
                T.epc = IFNULL(T.epc, S.rfid_id),
                T.hardwareKey = S.source,
                T.read_timestamp = CAST(S.received_at AS STRING),
                T.listing_id = S.listing_id,
                T.wh_name = S.warehouse_name
        """
        client.query(merge_query).result()
    except Exception as e:
        return {"status": "error", "stage": "merge", "message": str(e)}

    # ✅ log_processed_status に記録
    insert_query = f"""
        INSERT INTO `{processed_table}` (log_id, rfid_id, log_type, processed_at)
        VALUES (@log_id, @rfid_id, @log_type, CURRENT_TIMESTAMP())
    """
    for row in valid_rows:
        try:
            client.query(insert_query, job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("log_id", "STRING", row["log_id"]),
                    bigquery.ScalarQueryParameter("rfid_id", "STRING", row["rfid_id"]),
                    bigquery.ScalarQueryParameter("log_type", "STRING", "picking")
                ]
            )).result()
        except Exception as e:
            return {"status": "error", "stage": "log_processed_status insert", "message": str(e)}

    # ✅ スキップログ出力
    if skipped_logs:
        log_skipped_rows(skipped_logs, log_type="picking")

    return {"status": "success", "updated": len(valid_rows), "skipped": len(skipped_logs)}
