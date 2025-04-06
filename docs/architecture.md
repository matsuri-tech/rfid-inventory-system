# 🧩 システム全体構成とアーキテクチャ

## 概要
AppSheet → Cloud Run (FastAPI) → BigQuery による RFID在庫管理システム

## 主な構成要素
- **AppSheet**: 入力 UI（RFID登録・棚卸）
- **GCE**:大型RFIDのhttp->httpsプロキシサーバー用
- **Cloud Run + FastAPI**: 整形処理・在庫更新処理の API
- **BigQuery**: データベース（log, inventory, マスタ類）
- **Cloud Scheduler**: 定期実行による同期制御

## データフロー
1. AppSheet → temp テーブルへ登録
2. Cloud Run → temp テーブルを整形 → log テーブルへ
3. Cloud Run → log テーブルから在庫テーブル（t_commodity_rfid）へ MERGE
4. log_processed_status にログを書き、重複処理防止

## 特徴
- Pub/Sub 非採用（在庫更新は逐次的に確実性重視）
- Cloud Tasks や Cloud Scheduler による柔軟なキュー制御
- BigQuery の MERGE を活用したシンプルな更新


## サービス登録記録
- **BigQuery**
- スケジュールクエリ
- ・logi_tasks_headersテーブルの更新処理
- ・logi_リネン物流_ピッキングリスト取得更新
- ・logi_picking_logsテーブル定期更新

- **Cloud Scheduler**
- ジョブ名
- ・picking-sync-job      5分に1回実行
- ・picking-update-job    5分に1回実行


## 🧩 処理制御・ログ記録

...

### 🚫 スキップログ記録（共通機構）

整形処理や在庫更新に失敗したレコードを記録することで、
処理対象外となったデータを可視化・再利用可能にします。

- `log_skipped_rfid` テーブルに記録（共通）
- 各モジュールからの共通利用を想定（今後utilsに処理関数化予定）


🧭 現在の進捗ポイント（保持中）：

Cloud Runバッチ /batch/inventory-full-update：完成済み

log_skipped_rfid：共通化・ユーティリティ化済み

log_processed_status：rfid_idベース＆バッチ側で管理統一済み

倉庫マスタ＋選択管理テーブル：AppSheet構築進行中

AppSheetフォームでのSKU参照・内訳表示: 設計整理済み

scheduler.md：更新完了

次の作業候補：AppSheet倉庫設定画面の実装 or Cloud Logging / Slack 通知