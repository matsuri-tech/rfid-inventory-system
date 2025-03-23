from fastapi import APIRouter, Request
from datetime import datetime
from google.cloud import bigquery
from google.auth import default
from google.auth.transport.requests import Request as AuthRequest
import gspread
import pytz

router = APIRouter()

@router.post("/sync/large-rfid")
async def sync_large_rfid(request: Request):
    data = await request.json()
    hardware_key = data.get("hardwareKey")

    if not hardware_key:
        return {"error": "Missing hardwareKey"}, 400

    # Cloud Run 認証で gspread 使用
    creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
    creds.refresh(AuthRequest())
    gc = gspread.authorize(creds)

    # スプレッドシート情報
    SPREADSHEET_ID = "1EKRhJc5HlNulOIvg33OGrcrFAPuW6Cz_4nuZyoqsD3U"
    SHEET_NAME = "receiving_large_rfid_temp"
    sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    # データ取得
    data = sheet.get_all_records()
    if not data:
        return {"status": "no data in sheet"}, 200

    # フィルタ: processed=FALSE & hardwareKey一致
    filtered = [row for row in data if str(row.get("processed")).upper() != "TRUE" and row.get("hardwareKey") == hardware_key]

    # epcごとにread_timestampが最大の行を1件だけ取得
    latest_by_epc = {}
    for row in filtered:
        epc = row.get("epc")
        ts_raw = row.get("read_timestamp")
        if not epc or not ts_raw:
            continue
        try:
            ts = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if epc not in latest_by_epc or ts > latest_by_epc[epc]["read_timestamp_obj"]:
            row["read_timestamp_obj"] = ts
            latest_by_epc[epc] = row

    if not latest_by_epc:
        print(f"[DEBUG] Filtered row count: {len(filtered)}")
        print(f"[DEBUG] Sample filtered rows: {filtered[:2]}")
        return {"status": "no valid records"}, 200

    # BigQueryにINSERT
    client = bigquery.Client()
    log_table_id = "m2m-core.zzz_logistics.log_receiving_large_rfid"
    rows_to_insert = []

    for row in latest_by_epc.values():
        rows_to_insert.append({
            "id": row["id"],
            "read_timestamp": row["read_timestamp_obj"].isoformat(),
            "hardwareKey": row["hardwareKey"],
            "commandCode": row.get("commandCode"),
            "tagRecNums": row.get("tagRecNums"),
            "epc": row["epc"],
            "antNo": row.get("antNo"),
            "len": row.get("len"),
            "processed": False
        })

    errors = client.insert_rows_json(log_table_id, rows_to_insert)
    if errors:
        return {"error": "BigQuery insert failed", "details": errors}, 500

    return {"status": "ok", "synced": len(rows_to_insert)}

