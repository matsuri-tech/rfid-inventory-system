from fastapi import APIRouter
from google.cloud import bigquery
from datetime import datetime
from app.utils.logging_utils import log_skipped_rows  # 共通ログ関数

router = APIRouter()

@router.post("/receiving/update-inventory-large")
async def update_inventory_large():
    client = bigquery.Client()
    skipped_logs = []

    try:
        # ① 未処理ログ取得（log_id ベース）
        query = """
            SELECT *
            FROM `m2m-core.zzz_logistics.log_receiving_large_rfid` AS logs
            WHERE logs.processed = FALSE
              AND NOT EXISTS (
                SELECT 1
                FROM `m2m-core.zzz_logistics.log_processed_status` AS status
                WHERE status.log_id = logs.log_id
                  AND status.log_type = 'receiving'
              )
        """
        logs = list(client.query(query).result())
        if not logs:
            return {"status": "skipped", "reason": "no unprocessed logs"}

        valid_logs = []
        for row in logs:
            # バリデーション
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

        # スキップログが全件の場合
        if not valid_logs:
            log_skipped_rows(skipped_logs, log_type="receiving")
            return {
                "status": "skipped",
                "reason": "all invalid records",
                "skipped": len(skipped_logs)
            }

        # ② MERGE処理（ROW_NUMBERで1件に絞る）
        merge_query = """
            MERGE `m2m-core.zzz_logistics.t_commodity_rfid` T
            USING (
              SELECT *
              FROM (
                SELECT
                  rfid_id,
                  listing_id,
                  warehouse_name AS wh_name,
                  received_at AS read_timestamp,
                  rfid_id AS epc,
                  hardwareKey,
                  'receiving' AS status,
                  ROW_NUMBER() OVER (
                    PARTITION BY rfid_id
                    ORDER BY received_at DESC, CURRENT_TIMESTAMP() DESC
                  ) AS rn
                FROM `m2m-core.zzz_logistics.log_receiving_large_rfid`
                WHERE processed = FALSE
                  AND rfid_id IS NOT NULL
                  AND listing_id IS NOT NULL
                  AND warehouse_name IS NOT NULL
              )
              WHERE rn = 1
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

        # ③ log_processed_status に登録
        insert_query = """
            INSERT INTO `m2m-core.zzz_logistics.log_processed_status` (log_id, rfid_id, log_type)
            SELECT log_id, rfid_id, 'receiving'
            FROM `m2m-core.zzz_logistics.log_receiving_large_rfid`
            WHERE processed = FALSE
              AND rfid_id IS NOT NULL
              AND listing_id IS NOT NULL
              AND warehouse_name IS NOT NULL
        """
        client.query(insert_query).result()

        # ④ スキップログ出力（有効な行があった場合でも残りを記録）
        if skipped_logs:
            log_skipped_rows(skipped_logs, log_type="receiving")

        return {
            "status": "success",
            "updated": len(valid_logs),
            "skipped": len(skipped_logs)
        }

    except Exception as e:
        return {
            "status": "error",
            "stage": "inventory_update",
            "message": str(e)
        }, 500
