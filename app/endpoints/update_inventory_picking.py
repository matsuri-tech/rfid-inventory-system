from fastapi import APIRouter
from google.cloud import bigquery

router = APIRouter()

@router.post("/picking/update-inventory")
async def update_inventory_from_picking():
    client = bigquery.Client()

    log_table = "m2m-core.zzz_logistics.log_picking_rfid"
    inventory_table = "m2m-core.zzz_logistics.t_commodity_rfid"
    processed_table = "m2m-core.zzz_logistics.log_processed_status"

    # step 1: 未処理の log_id を判定
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
    log_rows = list(client.query(query).result())
    if not log_rows:
        return {"status": "skipped", "reason": "no unprocessed logs"}

    # step 2: MERGE 実行
    merge_query = f"""
        MERGE `{inventory_table}` T
        USING (
            SELECT rfid_id, listing_id, warehouse_name, source, received_at
            FROM `{log_table}`
            WHERE processed = FALSE
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
    try:
        client.query(merge_query).result()
    except Exception as e:
        return {"status": "error", "stage": "merge", "message": str(e)}

    # step 3: log_processed_status に登録
    insert_query = f"""
        INSERT INTO `{processed_table}` (log_id, rfid_id, log_type, processed_at)
        VALUES (@log_id, @rfid_id, @log_type, CURRENT_TIMESTAMP())
    """
    for row in log_rows:
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

    return {"status": "success", "updated": len(log_rows)}
