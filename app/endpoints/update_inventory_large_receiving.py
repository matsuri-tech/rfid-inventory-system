from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime

router = APIRouter()

@router.post("/sync/update_inventory_large_receiving")
async def update_inventory_large_receiving(request: Request):
    client = bigquery.Client()

    # Step 1: 未処理の log_receiving_large_rfid を取得
    fetch_query = """
        SELECT id, epc, hardwareKey
        FROM `m2m-core.zzz_logistics.log_receiving_large_rfid`
        WHERE processed = FALSE
        LIMIT 100
    """
    log_rows = [dict(row) for row in client.query(fetch_query)]

    if not log_rows:
        return {"status": "no unprocessed records"}

    updated_ids = []

    for row in log_rows:
        epc = row["epc"]
        hw_key = row["hardwareKey"]
        log_id = row["id"]

        # dev_m_wh_eq から倉庫情報を取得
        wh_query = f"""
            SELECT string_field_0 AS listing_id,
                   string_field_1 AS wh_name
            FROM `m2m-core.zzz_logistics.dev_m_wh_eq`
            WHERE string_field_2 = @hardwareKey
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("hardwareKey", "STRING", hw_key)]
        )
        wh_result = list(client.query(wh_query, job_config=job_config))

        if not wh_result:
            continue

        wh_info = dict(wh_result[0])

        # rfid_id = epc の在庫を更新
        update_inventory_query = f"""
            UPDATE `m2m-core.zzz_logistics.t_commodity_rfid`
            SET
                epc = @epc,
                hardwareKey = @hardwareKey,
                read_timestamp = CURRENT_TIMESTAMP(),
                listing_id = @listing_id,
                wh_name = @wh_name,
                status = "received"
            WHERE rfid_id = @epc
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("epc", "STRING", epc),
                bigquery.ScalarQueryParameter("hardwareKey", "STRING", hw_key),
                bigquery.ScalarQueryParameter("listing_id", "STRING", wh_info["listing_id"]),
                bigquery.ScalarQueryParameter("wh_name", "STRING", wh_info["wh_name"]),
            ]
        )
        client.query(update_inventory_query, job_config=job_config).result()
        updated_ids.append(f'"{log_id}"')

    # log_receiving_large_rfid の processed = TRUE に更新
    if updated_ids:
        update_log_query = f"""
            UPDATE `m2m-core.zzz_logistics.log_receiving_large_rfid`
            SET processed = TRUE
            WHERE id IN ({','.join(updated_ids)})
        """
        client.query(update_log_query).result()

    return {"status": "updated", "count": len(updated_ids)}
