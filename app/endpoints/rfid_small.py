from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime, timedelta
import ulid

router = APIRouter()

@router.post("/receiving/small-rfid")
async def receive_small_rfid(request: Request):
    data = await request.json()

    warehouse_name = data.get("warehouse_name")
    listing_id = data.get("listing_id")
    rfid_list_str = data.get("rfid_list")

    if not warehouse_name or not listing_id or not rfid_list_str:
        return {"error": "Missing required fields"}, 400

    # JST時刻に変換
    jst_time = (datetime.utcnow() + timedelta(hours=9)).isoformat()

    rfid_items = [r.strip() for r in rfid_list_str.split(",") if r.strip()]
    rows = []
    for rfid in rfid_items:
        row = {
            "log_id": str(ulid.new()),
            "rfid_id": rfid,
            "warehouse_name": warehouse_name,
            "listing_id": listing_id,
            "source": "AppSheet",
            "received_at": jst_time,
            "processed": False
        }
        rows.append(row)

    try:
        client = bigquery.Client()
        table_id = "m2m-core.zzz_logistics.log_receiving_small_rfid"
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            return {"error": "BigQuery insert failed", "details": errors}, 500
    except Exception as e:
        return {"error": "BigQuery error", "details": str(e)}, 500

    return {"status": "ok", "inserted": len(rows)}
