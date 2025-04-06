# 🧩 システム全体構成とアーキテクチャ

## 概要
AppSheet → Cloud Run (FastAPI) → BigQuery による RFID在庫管理システム

## 主な構成要素
- **AppSheet**: 入力 UI（RFID登録・棚卸）
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