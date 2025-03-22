from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime, timedelta
import ulid

router = APIRouter()

@router.post("/receiving/large-rfid")
async def receive_large_rfid(request: Request):
    data = await request.json()

    commandCode = data.get("commandCode")
    hardwareKey = data.get("hardwareKey")
    tagRecNums = data.get("tagRecNums")
    tagRecords = data.get("tagRecords", [])

    if not commandCode or not hardwareKey or not tagRecords:
        return {"error": "Missing required fields"}, 400

    timestamp = (datetime.utcnow() + timedelta(hours=9)).isoformat()
    rows = []
    for record in tagRecords:
        row = {
            "id": str(ulid.new()),
            "read_timestamp": timestamp,
            "hardwareKey": hardwareKey,
            "commandCode": commandCode,
            "tagRecNums": tagRecNums,
            "epc": record.get("Epc"),
            "antNo": record.get("antNo"),
            "len": record.get("Len")
        }
        rows.append(row)

    try:
        client = bigquery.Client()
        table_id = "m2m-core.zzz_logistics.log_receiving_large_rfid"
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            return {"error": "BigQuery insert failed", "details": errors}, 500
    except Exception as e:
        return {"error": "BigQuery error", "details": str(e)}, 500

    return {"status": "ok", "inserted": len(rows)}
