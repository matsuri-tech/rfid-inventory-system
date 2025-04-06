
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

# ⏱️ Cloud Scheduler の実行頻度とコスト設計

## ✅ 目的

各工程（Picking、Receiving など）で Cloud Run のAPIを自動実行するために、Cloud Scheduler を使用する。  
実行頻度の調整により、システムの即時性とコストのバランスを最適化する。

---

## 🔄 想定ユースケース

- AppSheet からの入力により temp テーブルが更新される
- Cloud Scheduler が定期的に Cloud Run API を叩くことで、
  - temp → log への整形処理
  - log → 在庫テーブルへの反映処理
  を自動で実施

---

## 🧮 実行頻度と月間実行数・コスト

| 頻度（cron） | 実行数/月（目安） | 料金（USD） | 備考 |
|---------------|--------------------|--------------|------|
| `*/5 * * * *`（5分ごと） | 約8,640回 | ~$0.86/月 | ✅開発・運用におすすめ |
| `* * * * *`（1分ごと） | 約43,200回 | ~$4.32/月 | 高頻度モニタリング向け |
| `0 * * * *`（毎時） | 約720回 | 無料（300件/月まで） | 低頻度バッチ処理用 |

> ※ 料金は東京リージョン、2025年時点の参考値。  
> ※ 最新の料金は [Cloud Scheduler 料金表](https://cloud.google.com/scheduler/pricing?hl=ja) を参照。

---

## 🛠️ 今回の設定方針（2025/04）

- **初期設定**：5分ごとの実行 `*/5 * * * *`
- **運用開始後**：
  - 利用状況を見ながら1分間隔への変更も検討
  - 実行ログやSlack通知連携を通じて運用確認を行う

---

## 🔐 認証について

Cloud Scheduler → Cloud Run の呼び出しには、サービスアカウントに  
**`roles/run.invoker`** 権限を付与して実行。

---

## 📎 実行対象API（例）

| 処理名 | URL |
|--------|-----|
| Picking整形 | `/picking/sync-picking` |
| 在庫更新（Picking） | `/picking/update-inventory` |
| Receiving整形 | `/sync/large-rfid` |
| 在庫更新（Receiving） | `/sync/update_inventory_large_receiving` |

---

## 📅 スケジューラ管理のベストプラクティス

- ✅ ジョブ名に `工程名 + 動作` を含める（例: `picking-sync-job`）
- ✅ リージョンは `asia-northeast1`（東京）で統一
- ✅ 手動実行 → Cloud Run ログ確認 → 安定確認後に有効化

---