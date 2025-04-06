# 🏷 Picking 処理仕様

## 処理対象
- `picking_logs_detail_temp` テーブル（整形前）
- `log_picking_rfid` テーブル（整形後）

## 処理概要
1. `selected_sku = 'END'` のデータを取得
2. RFID一覧（カンマ区切り）を展開
3. `wo_cleaning_tour` から `listing_id`, `warehouse_name` をJOIN
4. `log_picking_rfid` に書き込み
5. `log_processed_status` に `log_id` を記録
6. `t_commodity_rfid` に MERGE（在庫ステータスを"Picking"に更新）

## 処理ステータス管理
- `is_formatted`, `is_processing` で整形処理状態を管理
- `log_processed_status` によって重複実行を防止