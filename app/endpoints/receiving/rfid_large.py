from fastapi import APIRouter, Request  # FastAPI の Request
from datetime import datetime, timedelta
import ulid
import gspread
from google.auth import default
from google.auth.transport.requests import Request as GoogleRequest  # ← 別名で取り込む

router = APIRouter()

@router.post("/receiving/large-rfid/")
async def receive_large_rfid(request: Request):  # FastAPIのリクエスト型
    data = await request.json()

    commandCode = data.get("commandCode")
    hardwareKey = data.get("hardwareKey")
    tagRecNums = data.get("tagRecNums")
    tagRecords = data.get("tagRecords", [])

    if not commandCode or not hardwareKey or not tagRecords:
        return {"error": "Missing required fields"}, 400

    timestamp = (datetime.utcnow() + timedelta(hours=9)).isoformat()

    creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
    creds.refresh(GoogleRequest())  # ← Googleのリクエスト型
    client = gspread.authorize(creds)

    spreadsheet_id = "1EKRhJc5HlNulOIvg33OGrcrFAPuW6Cz_4nuZyoqsD3U"
    sheet_name = "receiving_large_rfid_temp"
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(sheet_name)

    for record in tagRecords:
        row = [
            str(ulid.new()),
            timestamp,
            hardwareKey,
            record.get("Epc"),
            commandCode,
            tagRecNums,
            record.get("antNo"),
            record.get("Len"),
            "FALSE",
            "FALSE"
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")

    return {"status": "ok", "inserted": len(tagRecords)}
