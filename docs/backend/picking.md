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

# 📦 Picking工程 Cloud Scheduler 設定記録

## 🎯 目的

AppSheet 経由で登録された Picking の一時テーブルを自動的に整形・在庫テーブルに反映するため、  
Cloud Scheduler を用いて FastAPI (Cloud Run) の各エンドポイントを5分間隔で自動実行する。

---

## 🔁 実行対象エンドポイント

| 処理 | URL |
|------|-----|
| Picking整形 | `https://rfid-cloud-api-829912128848.asia-northeast1.run.app/picking/sync-picking` |
| 在庫更新    | `https://rfid-cloud-api-829912128848.asia-northeast1.run.app/picking/update-inventory` |

---

## 🛠️ 設定手順（Cloud Scheduler）

### ✅ 方法1：Cloud Console（UI）

1. [Cloud Scheduler](https://console.cloud.google.com/cloudscheduler) を開く
2. 「ジョブを作成」をクリック
3. 以下の2つのジョブを作成する：

#### 🔹 ジョブ1：`picking-sync-job`

| 項目 | 設定値 |
|------|--------|
| 名前 | picking-sync-job |
| 頻度 | `*/5 * * * *` |
| ターゲット | HTTP |
| URL | `https://rfid-cloud-api-829912128848.asia-northeast1.run.app/picking/sync-picking` |
| HTTPメソッド | POST |
| 認証 | `Cloud Run呼び出し可能なサービスアカウント` を選択 |

#### 🔹 ジョブ2：`picking-update-job`

| 項目 | 設定値 |
|------|--------|
| 名前 | picking-update-job |
| 頻度 | `*/5 * * * *` |
| ターゲット | HTTP |
| URL | `https://rfid-cloud-api-829912128848.asia-northeast1.run.app/picking/update-inventory` |
| HTTPメソッド | POST |
| 認証 | `Cloud Run呼び出し可能なサービスアカウント` を選択 |

---

### ✅ 方法2：gcloud CLI を使う場合（参考）

```bash
# 🌀 Picking整形
gcloud scheduler jobs create http picking-sync-job \
  --schedule "*/5 * * * *" \
  --http-method POST \
  --uri "https://rfid-cloud-api-829912128848.asia-northeast1.run.app/picking/sync-picking" \
  --oauth-service-account-email "your-service-account@your-project.iam.gserviceaccount.com" \
  --time-zone "Asia/Tokyo"

# 🌀 在庫更新
gcloud scheduler jobs create http picking-update-job \
  --schedule "*/5 * * * *" \
  --http-method POST \
  --uri "https://rfid-cloud-api-829912128848.asia-northeast1.run.app/picking/update-inventory" \
  --oauth-service-account-email "your-service-account@your-project.iam.gserviceaccount.com" \
  --time-zone "Asia/Tokyo"