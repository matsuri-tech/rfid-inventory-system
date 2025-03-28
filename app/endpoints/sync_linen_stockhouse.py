from fastapi import APIRouter, Request
from google.auth import default
from google.auth.transport.requests import Request as GRequest
from google.cloud import bigquery
from datetime import datetime
import gspread

router = APIRouter()

@router.post("/sync/linen-stockhouse")
async def sync_linen_stock_from_sheet(request: Request):
    # 認証・スプレッドシート接続
    creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
    creds.refresh(GRequest())
    gc = gspread.authorize(creds)

    # BigQuery クライアント
    bq_client = bigquery.Client(credentials=creds, project="m2m-core")

    # シート取得
    ss = gc.open_by_key("1HhMIHJKBCbqkApnBk4gPZ0pkbKlRzwgee9-tr8VFlsU")
    entry_ws = ss.worksheet("linen_stock_entry_form")
    stock_ws = ss.worksheet("t_current_inventory")
    vertical_ws = ss.worksheet("linen_stock_entry_form_vertical")

    # データ取得
    entry_data = entry_ws.get_all_values()
    stock_data = stock_ws.get_all_values()

    # ヘッダー
    entry_header = entry_data[0]
    entry_rows = entry_data[1:]
    stock_header = stock_data[0]
    stock_rows = stock_data[1:]

    # SKUマッピング
    sku_map = {
        "BathMat": "537545",
        "BathTowel": "847415",
        "DoubleDuvetCover": "486613",
        "DoubleSheets": "747762",
        "HandTowel": "358431",
        "SingleDuvetCover": "276665",
        "pillowcase": "170662",
        "singleSheets": "738653"
    }
    sku_cols = {k: entry_header.index(k) for k in sku_map}
    processed_col = entry_header.index("処理済")
    today = datetime.now().strftime("%Y-%m-%d")
    updated_rows = 0

    # ✅ 在庫更新
    for i, row in enumerate(entry_rows):
        if len(row) <= processed_col or row[processed_col].strip() == "✔️":
            continue

        warehouse_id = row[3]
        kubun = row[5]
        delta_sign = -1 if "出庫" in kubun else 1

        for sku_name, col_index in sku_cols.items():
            try:
                qty = int(row[col_index]) if row[col_index] else 0
            except:
                qty = 0
            if qty == 0:
                continue

            sku_id = sku_map[sku_name]
            match_index = next((j for j, s_row in enumerate(stock_rows)
                                if s_row[0] == warehouse_id and s_row[2] == sku_id), None)

            if match_index is not None:
                before = int(stock_rows[match_index][4] or "0")
                after = before + delta_sign * qty
                stock_rows[match_index][4] = str(after)
                stock_rows[match_index][5] = today
                updated_rows += 1

        # ✔️フラグ
        entry_ws.update_cell(i + 2, processed_col + 1, "✔️")

    stock_ws.update("A2", stock_rows)

    # ✅ 縦持ち変換処理（修正バージョン）
    vertical_data = []
    fixed_cols = 6  # transaction_id, 日付, ユーザー, 倉庫ID, 倉庫名, 区分

    for row in entry_rows:
        if len(row) < fixed_cols:
            continue

        base = row[:fixed_cols]  # transaction_id〜区分

        for i in range(fixed_cols, len(entry_header)):
            sku_name = entry_header[i]
            try:
                value = int(row[i]) if row[i] else 0
            except:
                value = 0
            if value != 0:
                vertical_data.append(base + [sku_name, value])

    # スプレッドシート出力（任意）
    vertical_ws.clear()
    vertical_ws.append_row(["transaction_id", "日付", "ユーザー", "倉庫ID", "倉庫名", "区分", "SKU名", "数量"])
    if vertical_data:
        vertical_ws.append_rows(vertical_data)

    # ✅ BigQuery に登録
    if vertical_data:
        table_id = "m2m-core.zzz_logistics_line_stockhouse.linen_stock_entry_form"
        rows_to_insert = [
            {
                "transaction_id": row[0],
                "entry_date": datetime.strptime(row[1], "%Y/%m/%d %H:%M:%S"),
                "user_email": row[2],
                "warehouse_id": row[3],
                "warehouse_name": row[4],
                "category": row[5],
                "sku_name": row[6],
                "quantity": int(row[7])
            }
            for row in vertical_data
        ]

        errors = bq_client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            return {"status": "error", "details": errors}

    return {
        "status": "ok",
        "updated_stock_rows": updated_rows,
        "vertical_records_created": len(vertical_data)
    }
