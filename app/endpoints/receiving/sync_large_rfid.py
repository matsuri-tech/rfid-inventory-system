from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime
import gspread
from google.auth import default
from google.auth.transport.requests import Request as GRequest

router = APIRouter()

@router.post("/sync/large-rfid")
async def sync_large_rfid(request: Request):
    data = await request.json()
    hardware_key = data.get("hardwareKey")

    if not hardware_key:
        return {"error": "Missing hardwareKey"}, 400

    # Google Sheetsからデータ取得
    creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    creds.refresh(GRequest())
    client_sheets = gspread.authorize(creds)

    sheet = client_sheets.open_by_key("1EKRhJc5HlNulOIvg33OGrcrFAPuW6Cz_4nuZyoqsD3U").worksheet("receiving_large_rfid_temp")
    values = sheet.get_all_values()
    headers = values[0]
    rows = values[1:]

    # header index
    idx = {h: i for i, h in enumerate(headers)}

    # 未処理かつ対象ハードウェアキーの行を抽出
    filtered_rows = [
        row for row in rows
        if row[idx["hardwareKey"]] == hardware_key and row[idx["processed"]].strip().lower() == "false"
    ]

    if not filtered_rows:
        print("[DEBUG] No matching rows after filtering")
        return {"status": "no unprocessed rows found"}, 200

    # BigQueryクライアント
    client_bq = bigquery.Client()
    log_table_id = "m2m-core.zzz_logistics.log_receiving_large_rfid"

    # すでに存在するIDを確認
    target_ids = [f'"{row[idx["id"]]}"' for row in filtered_rows if row[idx["id"]]]
    if not target_ids:
        return {"status": "no IDs found"}, 200

    existing_ids_query = f"""
        SELECT id FROM `{log_table_id}` WHERE id IN ({','.join(target_ids)})
    """
    existing_ids_result = client_bq.query(existing_ids_query).result()
    existing_ids = set(row["id"] for row in existing_ids_result)

    # 重複を除外した行だけを挿入対象に
    rows_to_insert = []
    for row in filtered_rows:
        if row[idx["id"]] in existing_ids:
            continue

        rows_to_insert.append({
            "id": row[idx["id"]],
            "read_timestamp": row[idx["read_timestamp"]],
            "hardwareKey": row[idx["hardwareKey"]],
            "commandCode": row[idx["commandCode"]],
            "tagRecNums": row[idx["tagRecNums"]],
            "epc": row[idx["epc"]],
            "antNo": row[idx["antNo"]],
            "len": row[idx["len"]],
            "processed": False,
        })

    if not rows_to_insert:
        print("[DEBUG] All rows already inserted")
        return {"status": "no new rows"}, 200

    errors = client_bq.insert_rows_json(log_table_id, rows_to_insert, skip_invalid_rows=False)
    if errors:
        print(f"[ERROR] Insert errors: {errors}")
        return {"error": "Insert failed", "details": errors}, 500

    print(f"[SUCCESS] Inserted {len(rows_to_insert)} rows to {log_table_id}")
    print(f"[DEBUG] Inserted rows: {rows_to_insert}")
    return {"status": "ok", "inserted": len(rows_to_insert)}
