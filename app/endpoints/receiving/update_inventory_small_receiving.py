from fastapi import APIRouter
from google.cloud import bigquery
from datetime import datetime

router = APIRouter()

@router.post("/receiving/update-inventory-small")
async def update_inventory_small():
    client = bigquery.Client()

    skipped_logs = []

    try:
        # 未処理データ取得
        query = """
            SELECT *
            FROM `m2m-core.zzz_logistics.log_receiving_small_rfid` AS logs
            WHERE logs.processed = FALSE
              AND NOT EXISTS (
                SELECT 1
                FROM `m2m-core.zzz_logistics.log_processed_status` AS status
                WHERE status.rfid_id = logs.rfid_id
                  AND status.log_type = 'receiving'
              )
        """
        logs = list(client.query(query).result())
        if not logs:
            return {"status": "skipped", "reason": "no unprocessed logs"}

        valid_logs = []
        for row in logs:
            # バリデーション: listing_id, warehouse_name, rfid_id
            if not row["rfid_id"] or not row["listing_id"] or not row["warehouse_name"]:
                skipped_logs.append({
                    "log_id": row["log_id"],
                    "rfid_id": row["rfid_id"],
                    "reason": "missing field(s)",
                    "received_at": row.get("received_at"),
                    "logged_at": datetime.utcnow().isoformat()
                })
                continue

            valid_logs.append(row)

        if not valid_logs:
            return {"status": "skipped", "reason": "all invalid records", "skipped": len(skipped_logs)}

        # MERGE 在庫更新
        merge_query = """
            MERGE `m2m-core.zzz_logistics.t_commodity_rfid` T
            USING (
              SELECT
                rfid_id,
                listing_id,
                warehouse_name AS wh_name,
                received_at AS read_timestamp,
                rfid_id AS epc,
                'AppSheet' AS hardwareKey,
                'receiving' AS status
              FROM `m2m-core.zzz_logistics.log_receiving_small_rfid`
              WHERE processed = FALSE
                AND rfid_id IS NOT NULL
                AND listing_id IS NOT NULL
                AND warehouse_name IS NOT NULL
            ) S
            ON T.rfid_id = S.rfid_id
            WHEN MATCHED THEN
              UPDATE SET
                T.status = S.status,
                T.listing_id = S.listing_id,
                T.read_timestamp = CAST(S.read_timestamp AS STRING),
                T.hardwareKey = S.hardwareKey,
                T.wh_name = S.wh_name,
                T.epc = S.epc
        """
        client.query(merge_query).result()

        # 処理済みログ記録
        insert_log_query = """
            INSERT INTO `m2m-core.zzz_logistics.log_processed_status` (rfid_id, log_type)
            SELECT rfid_id, 'receiving'
            FROM `m2m-core.zzz_logistics.log_receiving_small_rfid`
            WHERE processed = FALSE
              AND rfid_id IS NOT NULL
              AND listing_id IS NOT NULL
              AND warehouse_name IS NOT NULL
        """
        client.query(insert_log_query).result()

        # 🚫 スキップログも書き出す
        if skipped_logs:
            client.insert_rows_json(
                "m2m-core.zzz_logistics.log_skipped_receiving_small_rfid",
                skipped_logs
            )

        return {
            "status": "success",
            "updated": len(valid_logs),
            "skipped": len(skipped_logs)
        }

    except Exception as e:
        return {"status": "error", "stage": "inventory_update", "message": str(e)}, 500
