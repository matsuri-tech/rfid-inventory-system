from fastapi import APIRouter, Request
from datetime import datetime, timezone
from google.cloud import bigquery
from google.auth import default
from google.auth.transport.requests import Request as AuthRequest
import gspread

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
    records = sheet.get_all_records()
    if not records:
        return {"status": "no data in sheet"}, 200

    # フィルタ: processed = FALSE & hardwareKey 一致
    filtered = [
        row for row in records
        if str(row.get("processed")).upper() != "TRUE" and row.get("hardwareKey") == hardware_key
    ]

    # epc ごとに最新 read_timestamp の行だけを残す
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
        print("[DEBUG] No matching rows after filtering")
        return {"status": "no valid records"}, 200

    # BigQuery insert 用データ整形
    client = bigquery.Client()
    table_id = "m2m-core.zzz_logistics.log_receiving_large_rfid"
    rows_to_insert = []

    for row in latest_by_epc.values():
        rows_to_insert.append({
            "id": str(row["id"]),
            "read_timestamp": row["read_timestamp_obj"].replace(tzinfo=timezone.utc).isoformat(),  # RFC3339
            "hardwareKey": str(row["hardwareKey"]),
            "commandCode": str(row.get("commandCode") or ""),
            "tagRecNums": str(row.get("tagRecNums") or ""),
            "epc": str(row["epc"]),
            "antNo": str(row.get("antNo") or ""),
            "len": str(row.get("len") or ""),
            "processed": False
        })

    errors = client.insert_rows_json(log_table_id, rows_to_insert, skip_invalid_rows=False)
    if errors:
        print(f"[ERROR] BigQuery insert failed: {errors}")
        return {"error": "Insert failed", "details": errors}, 500
    else:
        print(f"[SUCCESS] Inserted {len(rows_to_insert)} rows to {log_table_id}")
        print(f"[DEBUG] Inserted rows: {rows_to_insert}")

    print(f"[SUCCESS] Inserted {len(rows_to_insert)} rows to {table_id}")
    return {"status": "ok", "synced": len(rows_to_insert)}
