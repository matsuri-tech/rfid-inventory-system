# 📦 在庫更新処理仕様（inventory_update）

## 概要

`log_picking_rfid` などの整形済みログテーブルを元に、
在庫管理テーブル `t_commodity_rfid` を最新の状態に更新する処理です。
処理は Cloud Run の FastAPI 経由で定期的に呼び出されます。

---

## 対象テーブル

- ログテーブル例:
  - `log_picking_rfid`
  - `log_receiving_small_rfid`
- 在庫テーブル: `t_commodity_rfid`
- 処理済み記録テーブル: `log_processed_status`

---

## 更新内容（MERGE先）

| カラム名           | 更新値のソース                     |
|--------------------|-----------------------------------|
| `status`           | 工程名（例："Picking"）            |
| `epc`              | なければ `rfid_id` をそのまま     |
| `hardwareKey`      | `source` カラムをそのまま使用      |
| `read_timestamp`   | `received_at` を文字列変換         |
| `listing_id`       | `listing_id` from log             |
| `wh_name`          | `warehouse_name` from log         |

---

## 処理ステップ

1. `log_processed_status` に存在しない `rfid_id`, `log_type` をログテーブルから抽出
2. `t_commodity_rfid` に対して `MERGE` による更新処理を実行
3. 更新後、`log_processed_status` に `rfid_id`, `log_type`, `processed_at` を記録

---

## 注意点・工夫点

- **Streaming Buffer制限回避**：ログテーブルの `processed` フラグ更新をやめ、
  代わりに `log_processed_status` テーブルを導入。
- **重複更新の防止**：`rfid_id + log_type` のユニーク性で実現。
- **循環型処理に対応**：一度使用された `rfid_id` が再度流通するケースも想定し、
  重複登録を許容。

---

## 補足

- `log_processed_status` により MERGE 対象をフィルタリングできるため、
  全件取得の負荷が軽減される。
- 今後、`shipping`, `cleaning`, `inspection` 等の工程も同様の方式で統一可能。