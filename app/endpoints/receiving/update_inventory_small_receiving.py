from fastapi import APIRouter
from google.cloud import bigquery
from datetime import datetime

router = APIRouter()

@router.post("/receiving/update-inventory-small")
async def update_inventory_small():
    client = bigquery.Client()

    try:
        # ① 未処理のレコード抽出（log_processed_statusに存在しないもの）
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

        # ② 在庫更新（MERGE）
        merge_query = """
            MERGE `m2m-core.zzz_logistics.t_commodity_rfid` T
            USING (
              SELECT
                rfid_id,
                listing_id,
                warehouse_name AS wh_name,
                received_at AS read_timestamp,
                COALESCE(rfid_id, epc) AS epc,
                'AppSheet' AS hardwareKey,
                'receiving' AS status
              FROM `m2m-core.zzz_logistics.log_receiving_small_rfid`
              WHERE processed = FALSE
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

        # ③ log_processed_statusに登録
        insert_log_query = """
            INSERT INTO `m2m-core.zzz_logistics.log_processed_status` (rfid_id, log_type)
            SELECT rfid_id, 'receiving'
            FROM `m2m-core.zzz_logistics.log_receiving_small_rfid`
            WHERE processed = FALSE
        """
        client.query(insert_log_query).result()

        # ④ log_receiving_small_rfid.processed を TRUE に更新（※streaming bufferには注意）
        # 今回は実行しない、別で処理記録テーブルだけ使う形に統一する設計

        return {"status": "success", "updated": len(logs)}

    except Exception as e:
        return {"status": "error", "stage": "inventory_update", "message": str(e)}, 500
