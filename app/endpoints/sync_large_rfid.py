from fastapi import APIRouter, Request
from google.cloud import bigquery
from google.auth import default
from google.auth.transport.requests import Request as GoogleRequest
import gspread
from datetime import datetime
import pytz

router = APIRouter()

@router.post("/sync/large-rfid")
async def sync_large_rfid(request: Request):
    data = await request.json()
    hardware_key = data.get("hardwareKey")

    if not hardware_key:
        return {"error": "Missing hardwareKey"}, 400

    # スプレッドシート認証
    creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    creds.refresh(GoogleRequest())
    client_gs = gspread.authorize(creds)

    sheet = client_gs.open_by_key("1EKRhJc5HlNulOIvg33OGrcrFAPuW6Cz_4nuZyoqsD3U")
    worksheet = sheet.worksheet("receiving_large_rfid_temp")
    records = worksheet.get_all_records()

    # hardwareKey一致 + processed = FALSE の行のみ抽出
    target_rows = [
        r for r in records
        if r.get("hardwareKey") == hardware_key and str(r.get("processed")).upper() == "FALSE"
    ]

    if not target_rows:
        print("[DEBUG] No matching rows after filtering")
        return {"status": "no unprocessed rows found"}

    # UTCのタイムスタンプをBigQuery用に調整
    for r in target_rows:
        if isinstance(r.get("read_timestamp"), str):
            try:
                r["read_timestamp"] = datetime.fromisoformat(r["read_timestamp"].replace("Z", "+00:00"))
            except:
                r["read_timestamp"] = datetime.utcnow()

    # BigQueryクライアント
    client_bq = bigquery.Client()
    log_table_id = "m2m-core.zzz_logistics.log_receiving_large_rfid"

    # すでに存在するIDの除外
    id_list = [f'"{r["id"]}"' for r in target_rows if r.get("id")]
    check_query = f"""
        SELECT id FROM `{log_table_id}`
        WHERE id IN ({','.join(id_list)})
    """
    existing_ids = set(row["id"] for row in client_bq.query(check_query))

    # 重複除去済みの行を整形
    rows_to_insert = []
    for r in target_rows:
        if r["id"] in existing_ids:
            continue
        rows_to_insert.append({
            "id": r["id"],
            "read_timestamp": r["read_timestamp"],
            "hardwareKey": r["hardwareKey"],
            "commandCode": r["commandCode"],
            "tagRecNums": r["tagRecNums"],
            "epc": r["epc"],
            "antNo": r["antNo"],
            "len": r["len"],
            "processed": False  # 常にFalseで書き込み
        })

    if not rows_to_insert:
        print("[DEBUG] No new rows to insert")
        return {"status": "already synced"}

    # BigQueryにINSERT
    errors = client_bq.insert_rows_json(log_table_id, rows_to_insert, skip_invalid_rows=False)

    if errors:
        print("[ERROR] Insert errors:", errors)
        return {"error": "Insert failed", "details": errors}, 500

    print(f"[SUCCESS] Inserted {len(rows_to_insert)} rows to {log_table_id}")
    print(f"[DEBUG] Inserted rows: {rows_to_insert}")
    return {"status": "ok", "inserted": len(rows_to_insert)}

