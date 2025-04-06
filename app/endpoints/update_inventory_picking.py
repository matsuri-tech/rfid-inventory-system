from fastapi import APIRouter
from google.cloud import bigquery

router = APIRouter()

@router.post("/picking/update-inventory")
async def update_inventory_from_picking():
    client = bigquery.Client()

    log_table = "m2m-core.zzz_logistics.log_picking_rfid"
    inventory_table = "m2m-core.zzz_logistics.t_commodity_rfid"

    # step 1: 未処理のRFIDログを取得
    query = f"""
        SELECT *
        FROM `{log_table}`
        WHERE processed = FALSE
        LIMIT 100
    """
    log_rows = list(client.query(query).result())
    if not log_rows:
        return {"status": "skipped", "reason": "no unprocessed logs"}

    rfid_ids = [row["rfid_id"] for row in log_rows]
    log_data = {row["rfid_id"]: row for row in log_rows}

    # step 2: MERGEで在庫テーブルを更新
    # 一時テーブル用データ構築
    temp_table_name = "log_picking_merge_temp"
    dataset_ref = client.dataset("zzz_logistics")
    table_ref = dataset_ref.table(temp_table_name)

    # 作業用一時テーブルを作成
    rows_to_insert = []
    for row in log_rows:
        rows_to_insert.append({
            "rfid_id": row["rfid_id"],
            "listing_id": row["listing_id"],
            "warehouse_name": row["warehouse_name"],
            "source": row["source"],
            "received_at": row["received_at"]
        })

    # スキーマ定義（必要なカラムのみ）
    schema = [
        bigquery.SchemaField("rfid_id", "STRING"),
        bigquery.SchemaField("listing_id", "STRING"),
        bigquery.SchemaField("warehouse_name", "STRING"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("received_at", "DATETIME"),
    ]

    client.delete_table(table_ref, not_found_ok=True)
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table)
    client.insert_rows_json(table, rows_to_insert)

    # step 3: MERGE クエリで在庫更新
    merge_query = f"""
        MERGE `{inventory_table}` T
        USING `{log_table}` S
        ON T.rfid_id = S.rfid_id
        WHERE S.processed = FALSE
        WHEN MATCHED THEN
          UPDATE SET
            T.status = 'Picking',
            T.epc = IFNULL(T.epc, S.rfid_id),
            T.hardwareKey = S.source,
            T.read_timestamp = S.received_at,
            T.listing_id = S.listing_id,
            T.wh_name = S.warehouse_name
    """
    client.query(merge_query).result()

    # step 4: logテーブルを processed = TRUE に更新
    update_query = f"""
        UPDATE `{log_table}`
        SET processed = TRUE
        WHERE processed = FALSE
          AND rfid_id IN UNNEST(@rfid_list)
    """
    client.query(update_query, job_config=bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("rfid_list", "STRING", rfid_ids)
        ]
    )).result()

    return {"status": "success", "updated": len(rfid_ids)}
