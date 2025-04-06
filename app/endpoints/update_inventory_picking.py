from fastapi import APIRouter
from google.cloud import bigquery

router = APIRouter()

@router.post("/picking/update-inventory")
async def update_inventory_from_picking():
    client = bigquery.Client()

    log_table = "m2m-core.zzz_logistics.log_picking_rfid"
    inventory_table = "m2m-core.zzz_logistics.t_commodity_rfid"

    # step 1: 未処理のログ取得
    query = f"""
        SELECT rfid_id, listing_id, warehouse_name, source, received_at
        FROM `{log_table}`
        WHERE processed = FALSE
        LIMIT 100
    """
    log_rows = list(client.query(query).result())
    if not log_rows:
        return {"status": "skipped", "reason": "no unprocessed logs"}

    # step 2: MERGE クエリで在庫テーブルを更新
    merge_query = f"""
        MERGE `{inventory_table}` T
        USING (
            SELECT rfid_id, listing_id, warehouse_name, source, received_at
            FROM `{log_table}`
            WHERE processed = FALSE
            LIMIT 100
        ) S
        ON T.rfid_id = S.rfid_id
        WHEN MATCHED THEN
          UPDATE SET
            T.status = 'Picking',
            T.epc = IFNULL(T.epc, S.rfid_id),
            T.hardwareKey = S.source,
            T.read_timestamp = CAST(S.received_at AS STRING),  -- ★ 修正ポイント！
            T.listing_id = S.listing_id,
            T.wh_name = S.warehouse_name
    """
    try:
        client.query(merge_query).result()
    except Exception as e:
        return {"status": "error", "stage": "merge", "message": str(e)}

    # step 3: processed = TRUE に更新（安全なUNNEST）
    rfid_ids = [row["rfid_id"] for row in log_rows]
    if not rfid_ids:
        return {"status": "skipped", "reason": "no rfid_ids to update"}

    update_query = f"""
        UPDATE `{log_table}`
        SET processed = TRUE
        WHERE rfid_id IN UNNEST(@rfid_list)
    """
    try:
        client.query(update_query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("rfid_list", "STRING", rfid_ids)
            ]
        )).result()
    except Exception as e:
        return {"status": "error", "stage": "update processed", "message": str(e)}

    return {"status": "success", "updated": len(rfid_ids)}

