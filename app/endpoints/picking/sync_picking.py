from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime, timedelta
import ulid

router = APIRouter()

@router.post("/picking/sync-picking")
async def sync_small_picking_rfid(request: Request):
    client = bigquery.Client()

    # step 1: 整形対象の取得
    temp_table = "m2m-core.zzz_logistics_line_stockhouse.picking_logs_detail_temp"
    query = f"""
        SELECT *
        FROM `{temp_table}`
        WHERE selected_sku = 'END'
          AND is_formatted = FALSE
          AND is_processing = FALSE
        LIMIT 10
    """
    rows = list(client.query(query).result())

    if not rows:
        return {"status": "skipped", "reason": "no unformatted rows"}

    results = []
    for row in rows:
        cleaning_id = row["cleaning_id"]
        rfid_str = row["scanned_rfid_list_str"]
        log_id = row["log_id"] or f"log_{ulid.new().str.lower()}"

        if not rfid_str:
            continue

        rfid_list = [r.strip() for r in rfid_str.split(",") if r.strip()]

        # step 2: JOIN (wo_cleaning_tour) で listing_id / warehouse_name を取得
        join_query = """
            SELECT listing_id, room_name_common_area_name AS warehouse_name
            FROM `m2m-core.su_wo.wo_cleaning_tour`
            WHERE cleaning_id = @cleaning_id
            LIMIT 1
        """
        join_result = list(client.query(join_query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cleaning_id", "STRING", cleaning_id)
            ]
        )).result())

        if not join_result:
            continue  # skip if no match

        listing_id = join_result[0]["listing_id"]
        warehouse_name = join_result[0]["warehouse_name"]

        now_jst = (datetime.utcnow() + timedelta(hours=9)).isoformat()

        insert_rows = []
        for rfid in rfid_list:
            insert_rows.append({
                "log_id": log_id,
                "rfid_id": rfid,
                "warehouse_name": warehouse_name,
                "listing_id": listing_id,
                "source": "AppSheet",
                "received_at": now_jst,
                "processed": False
            })

        # step 3: INSERT into log_picking_rfid
        target_table = "m2m-core.zzz_logistics.log_picking_rfid"
        errors = client.insert_rows_json(target_table, insert_rows)
        if errors:
            return {"error": "insert_failed", "details": errors}, 500

        # step 4: 更新（is_formatted, is_processing）
        update_query = f"""
            UPDATE `{temp_table}`
            SET is_formatted = TRUE, is_processing = FALSE, log_id = @log_id
            WHERE cleaning_id = @cleaning_id
        """
        client.query(update_query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("log_id", "STRING", log_id),
                bigquery.ScalarQueryParameter("cleaning_id", "STRING", cleaning_id)
            ]
        )).result()

        results.append({"cleaning_id": cleaning_id, "inserted": len(insert_rows)})

    return {"status": "success", "results": results}

