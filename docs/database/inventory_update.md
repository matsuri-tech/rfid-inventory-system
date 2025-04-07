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
# 🔁 バッチ在庫更新処理仕様（inventory-full-update）

## 概要

Cloud Run 上の FastAPI アプリに `/batch/inventory-full-update` という専用エンドポイントを用意し、  
Cloud Scheduler により **定期的に在庫更新処理を一括実行** するバッチ機構です。

---

## 🔗 エンドポイント

POST /batch/inventory-full-update

yaml
コピーする
編集する

---

## ✅ 処理フロー

このバッチエンドポイントは、以下の 4 つのエンドポイントを **逐次実行**します：

| 順序 | 処理名                       | エンドポイント                          |
|------|------------------------------|------------------------------------------|
| ①   | 小型RFIDログ同期             | `/receiving/sync-small-rfid`            |
| ②   | 小型RFID在庫更新             | `/receiving/update-inventory-small`     |
| ③   | Pickingログ同期              | `/picking/sync-picking`                 |
| ④   | Picking在庫更新              | `/picking/update-inventory`             |

---

## 🧠 実装の特徴

- `httpx.AsyncClient` を使用し、**逐次POSTリクエスト**を送信
- 成功/失敗を個別にレスポンスに記録
- レスポンス構造：

```json
{
  "status": "completed",
  "results": [
    {
      "endpoint": "/receiving/sync-small-rfid",
      "status_code": 200,
      "response": {...}
    },
    {
      "endpoint": "/receiving/update-inventory-small",
      "status_code": 200,
      "response": {...}
    },
    ...
  ]
}
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

## ⚙️ 重複ログ処理の方針（rfid_id が複数存在する場合）

### 背景

RFIDログテーブル（例：`log_receiving_small_rfid`）には、同一 `rfid_id` のレコードが複数登録されているケースがあります。これらがすべて未処理状態である場合、BigQuery の `MERGE` にて「1行に対して複数行がマッチする」というエラーが発生します。

---

### 解決策：ROW_NUMBER による 1件選定

重複する `rfid_id` に対して、次のルールで1件のみを対象とします。

| 優先順位 | 条件 |
|----------|------|
| 1 | `received_at` が最新のもの |
| 2 | 同一 `received_at` の場合、後に挿入された行（`CURRENT_TIMESTAMP()` 降順） |

以下のクエリで実現します：

```sql
ROW_NUMBER() OVER (
  PARTITION BY rfid_id
  ORDER BY received_at DESC, CURRENT_TIMESTAMP() DESC
)
