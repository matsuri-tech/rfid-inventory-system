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

---

## 📉 スキップログ記録 (`log_skipped_rfid`)

### ✅ 目的

整形ログテーブル（`log_receiving_small_rfid` など）において、必須情報（`rfid_id`, `listing_id`, `warehouse_name`）が欠損しており、在庫更新に進めなかったデータを記録することで、  
データの不整合や処理漏れを可視化・検知可能とすることを目的としています。

---

### 🗃️ テーブル構成

`m2m-core.zzz_logistics.log_skipped_rfid`

| フィールド名 | 型        | 説明                              |
|--------------|-----------|-----------------------------------|
| `log_id`     | STRING    | 元ログテーブルの `log_id`         |
| `rfid_id`    | STRING    | スキップ対象の `rfid_id`          |
| `log_type`   | STRING    | 工程種別（例: `"receiving"`）     |
| `reason`     | STRING    | スキップ理由（例: `"missing field(s)"`） |
| `received_at`| DATETIME  | 元データの受信日時                |
| `logged_at`  | TIMESTAMP | スキップログの記録日時（現在時刻）|

---

## 💡 スキップログの共通ユーティリティ化

すべての在庫更新工程（receiving, picking など）で発生し得る不正・欠損データを記録するため、共通関数 `log_skipped_rows()` を `utils/logging_utils.py` に定義。

| カラム名        | 説明                              |
|----------------|-----------------------------------|
| `log_id`        | 対象レコードのログID             |
| `rfid_id`       | スキップ対象のRFID ID             |
| `log_type`      | 工程名（例: receiving, picking）   |
| `reason`        | スキップ理由（missing field等）  |
| `received_at`   | 元ログでの受信日時                |
| `logged_at`     | スキップログとして記録した日時     |

すべての工程でこの関数を呼び出すことで、処理の追跡性・原因特定を一元的に管理できるようになる。

---