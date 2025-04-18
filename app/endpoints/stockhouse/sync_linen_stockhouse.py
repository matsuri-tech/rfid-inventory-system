from fastapi import APIRouter, Request
from google.auth import default
from google.auth.transport.requests import Request as GRequest
from google.cloud import bigquery
from datetime import datetime
import gspread

router = APIRouter()

# ✅ 柔軟な日付パース関数を定義
def parse_date_flexible(date_str: str) -> datetime:
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unknown date format: {date_str}")

# ✅ datetimeをJSONシリアライズ可能に変換
def to_serializable_dict(row: dict) -> dict:
    return {
        key: (
            value.isoformat() if isinstance(value, datetime) else value
        )
        for key, value in row.items()
    }

@router.post("/sync/linen-stockhouse")
async def sync_linen_stock_from_sheet(request: Request):
    creds, _ = default(scopes=[
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/spreadsheets"
    ])
    creds.refresh(GRequest())

    gc = gspread.authorize(creds)
    bq_client = bigquery.Client(credentials=creds, project="m2m-core")

    ss = gc.open_by_key("1HhMIHJKBCbqkApnBk4gPZ0pkbKlRzwgee9-tr8VFlsU")
    entry_ws = ss.worksheet("linen_stock_entry_form")
    stock_ws = ss.worksheet("t_current_inventory")
    vertical_ws = ss.worksheet("linen_stock_entry_form_vertical")

    entry_data = entry_ws.get_all_values()
    stock_data = stock_ws.get_all_values()

    entry_header = entry_data[0]
    entry_rows = entry_data[1:]
    stock_header = stock_data[0]
    stock_rows = stock_data[1:]

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

    # ✅ 区分による入出庫判断用セット
    incoming_kubun = {"1_通常入庫", "2_追加発注入庫"}
    outgoing_kubun = {"3_通常出庫", "4_横持ち出庫", "5_不具合品"}

    for i, row in enumerate(entry_rows):
        if len(row) <= processed_col or row[processed_col].strip() == "✔️":
            continue

        warehouse_id = row[3]
        kubun = row[5]

        if kubun in outgoing_kubun:
            delta_sign = -1
        elif kubun in incoming_kubun:
            delta_sign = 1
        else:
            continue  # 不明な区分はスキップ

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

        entry_ws.update_cell(i + 2, processed_col + 1, "✔️")

    stock_ws.update("A2", stock_rows)

    # ✅ 縦持ちデータ作成
    vertical_data = []
    fixed_cols = 6

    for row in entry_rows:
        if len(row) < fixed_cols:
            continue

        base = row[:fixed_cols]
        kubun = base[5]

        if kubun not in incoming_kubun and kubun not in outgoing_kubun:
            continue

        for i in range(fixed_cols, len(entry_header)):
            sku_name = entry_header[i]
            try:
                value = int(row[i]) if row[i] else 0
            except:
                value = 0
            if value != 0:
                vertical_data.append(base + [sku_name, value])

    vertical_ws.clear()
    vertical_ws.append_row(["transaction_id", "日付", "ユーザー", "倉庫ID", "倉庫名", "区分", "SKU名", "数量"])
    if vertical_data:
        vertical_ws.append_rows(vertical_data)

    # ✅ BigQuery 在庫更新処理
    table_id = "m2m-core.zzz_logistics_line_stockhouse.t_current_inventory"

    for row in vertical_data:
        listing_id = row[3]
        kubun = row[5]
        sku_name = row[6]
        sku_id = sku_map.get(sku_name)
        qty = int(row[7])

        if kubun in outgoing_kubun:
            delta_sign = -1
        elif kubun in incoming_kubun:
            delta_sign = 1
        else:
            continue

        delta_qty = delta_sign * qty

        if not sku_id:
            continue

        query = f"""
            UPDATE `{table_id}`
            SET current_quantity = IFNULL(current_quantity, 0) + @delta_qty,
                recorded_at = CURRENT_DATE()
            WHERE listing_id = @listing_id
              AND SKU = @sku_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("delta_qty", "INT64", delta_qty),
                bigquery.ScalarQueryParameter("listing_id", "STRING", listing_id),
                bigquery.ScalarQueryParameter("sku_id", "STRING", sku_id),
            ]
        )

        bq_client.query(query, job_config=job_config).result()

    return {
        "status": "ok",
        "updated_stock_rows": updated_rows,
        "vertical_records_created": len(vertical_data)
    }
