from fastapi import APIRouter, Request
from google.cloud import bigquery
from datetime import datetime
import ulid

router = APIRouter()

@router.post("/sync/picking")
async def sync_picking(request: Request):
    client = bigquery.Client()

    # Step 1: 未処理データの取得
    query = """
        SELECT * FROM `m2m-core.logistics.t_temp_picking`
        WHERE processed = FALSE
    """
    rows = [dict(row) for row in client.query(query)]

    if not rows:
        return {"status": "no data"}

    insert_rows = []
    temp_ids = []  # UPDATE 用
    shipping_updates = []  # plan テーブル更新用

    for row in rows:
        rfid_list = [r.strip() for r in row.get("rfid_input_list_add", "").split(",") if r.strip()]
        for rfid in rfid_list:
            insert_rows.append({
                "id": str(ulid.new()),
                "picking_qr": row["picking_qr"],
                "rfid_id": rfid,
                "rfid_input_list_add": row["rfid_input_list_add"],
                "listing_name": row["listing_name"],
                "listing_id": row["listing_id"],
                "work_datetime": row["work_datetime"],
                "created_at": datetime.utcnow().isoformat(),
                "processed": False,
            })
        # 後で temp_picking 側 processed を true にする
        temp_ids.append(f'"{row["id"]}"')
        # shipping_plan 側も更新対象として記録
        shipping_updates.append({
            "cleaning_base_id": row["picking_qr"],
            "work_datetime": row["work_datetime"]
        })

    # Step 2: log_picking に挿入
    table_id = "m2m-core.zzz_logistics.log_picking"
    errors = client.insert_rows_json(table_id, insert_rows)
    if errors:
        return {"error": "Insert failed", "details": errors}, 500

    # Step 3: temp_picking.processed = TRUE
    update_temp_query = f"""
        UPDATE `m2m-core.zzz_logistics.t_temp_picking`
        SET processed = TRUE
        WHERE id IN ({','.join(temp_ids)})
    """
    client.query(update_temp_query).result()

    # Step 4: t_shipping_plan 更新（picking_done = TRUE, picking_done_at を設定）
    for u in shipping_updates:
        update_plan_query = f"""
            UPDATE `m2m-core.zzz_logistics.t_shipping_plan`
            SET picking_done = TRUE,
                picking_done_at = TIMESTAMP("{u['work_datetime']}")
            WHERE cleaning_base_id = "{u['cleaning_base_id']}"
        """
        client.query(update_plan_query).result()

    return {"status": "ok", "inserted_rows": len(insert_rows)}
