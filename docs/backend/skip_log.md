# 🚫 skip_log.md - スキップログ機構

---

## 🎯 目的

RFID在庫処理において、**正しく処理できなかったレコード（不備あり）を記録することで、原因追跡や再処理の基盤を提供**するための仕組みです。

---

## ✅ スキップの対象例

| 対象処理 | スキップされる理由（例） |
|----------|------------------------|
| Receiving | listing_id または warehouse_name が欠損 |
| Picking   | rfid_list の形式不正、関連 cleaning_id が見つからない |
| Shipping（予定） | 処理対象の SKU が不正、未定義リストとの紐付け失敗 |

---

## 🧱 ログテーブル構成

| カラム名 | 型 | 説明 |
|----------|----|------|
| `log_id` | STRING | スキップされたレコードの log_id（工程ごとに一意） |
| `rfid_id` | STRING | 対象のRFID（空の場合あり） |
| `reason` | STRING | スキップ理由（例：`missing listing_id`） |
| `received_at` | DATETIME | 元データの受信日時 |
| `logged_at` | TIMESTAMP | このスキップログが記録された時間 |

BigQuery テーブル名：  m2m-core.zzz_logistics.log_skipped_rfid

---

## 🔁 実装ポリシー

- 各工程（picking / receiving）にて、整形または在庫更新時にスキップ対象を抽出。
- `log_skipped_rfid` テーブルに `insert_rows_json` で追記。
- 同一テーブルで全工程のスキップログを集約（`log_type` カラムを追加してもOK）

---

## 💡 運用案

| 項目 | 内容 |
|------|------|
| スキップ記録期間 | 30日（定期削除も可） |
| 通知 | エラー件数が一定数を超えたら Slack / メール通知（今後対応） |
| 再処理 | 管理画面から再実行可能な仕組みを AppSheet または別UIで構築可能 |

---

## ✨ 今後の拡張

- `log_type` カラムの追加で、`receiving`, `picking`, `shipping` の区別を明確に。
- `skipped_by`（処理モジュール名）などで原因特定精度を向上。
