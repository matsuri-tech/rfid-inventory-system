
# 📆 scheduler.md（Cloud Scheduler設計）

## ✅ 目的
Cloud Scheduler により、各工程の整形・在庫更新処理を定期実行することで、ユーザーによる入力後の自動同期を実現します。

---

## 🛠️ 設定内容

| 項目 | 内容 |
|------|------|
| 実行先 | Cloud Run (FastAPI endpoint) |
| 実行間隔 | 5分間隔（`*/5 * * * *`）など工程ごとに調整可能 |
| HTTPメソッド | POST |
| 認証 | サービスアカウント＋IAMロール（Invoker）で制御 |

---

## 🔄 対象エンドポイント

| エンドポイント | 処理内容 |
|----------------|----------|
| `/picking/sync-picking` | Picking整形処理の実行 |
| `/picking/update-inventory` | 在庫更新（Picking） |
| `/receiving/large-rfid` | Receiving登録（AppSheet経由） |
| `/sync/large-rfid` | Large Receiving 整形処理（Cloud Run） |
| `/sync/update_inventory_large_receiving` | 在庫更新（Receiving） |

---

## 🧩 補足

- **ステートレス実行**：Cloud Run 側は常に最新データに対して処理を行うため、スケジューラ側はリクエスト送信のみでOK。
- **限定的な更新**：対象データは `is_formatted = FALSE`, `processed = FALSE` 等のフィルタ条件により制御。
- **ログ管理**：Cloud Logging にてエラー監視・アラート設定も推奨。
