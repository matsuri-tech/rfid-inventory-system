from fastapi import FastAPI, Request
from google.cloud import bigquery
from datetime import datetime
import ulid

app = FastAPI()

@app.post("/receive-small-rfid")
async def receive_tags(request: Request):
    data = await request.json()

    commandCode = data.get("commandCode")
    hardwareKey = data.get("hardwareKey")
    tagRecNums = data.get("tagRecNums")
    tagRecords = data.get("tagRecords", [])

    if not commandCode or not hardwareKey or not tagRecords:
        return {"error": "Missing required fields"}

    timestamp = datetime.utcnow().isoformat()
    rows = []

    for record in tagRecords:
        rows.append({
            "id": str(ulid.new()),
            "read_timestamp": timestamp,
            "hardwareKey": hardwareKey,
            "commandCode": commandCode,
            "tagRecNums": tagRecNums,
            "epc": record.get("Epc"),
            "antNo": record.get("antNo"),
            "len": record.get("Len"),
        })

    try:
        client = bigquery.Client()
        table_id = "m2m-core.zzz_logistics.log_receiving_small_rfid"
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            return {"error": "BigQuery insert failed", "details": errors}
    except Exception as e:
        return {"error": "BigQuery error", "details": str(e)}

    return {"status": "ok", "inserted": len(rows)}
