# 📆 scheduler.md（Cloud Scheduler設計）

## ✅ 目的

Cloud Scheduler により、各工程の整形・在庫更新処理を定期実行することで、ユーザーによる入力後の**自動同期**を実現します。  
現在は `/batch/inventory-full-update` を通じて、複数処理を **逐次的に1本でまとめて実行** できる構成としています。

---

## 🛠️ 設定内容

| 項目             | 内容 |
|------------------|------|
| 実行先           | Cloud Run（FastAPIエンドポイント） |
| 実行間隔         | `*/5 * * * *`（5分おき） ※調整可 |
| HTTPメソッド     | `POST` |
| タイムゾーン     | `Asia/Tokyo` |
| 認証方式         | サービスアカウント + `roles/run.invoker` |

---

## 🔁 実行対象エンドポイント

| エンドポイント | 説明 |
|----------------|------|
| `/batch/inventory-full-update` | 下記のすべての処理を逐次的に実行します（推奨） |

バッチ内で実行される子処理は以下：

1. `/receiving/sync-small-rfid`  
2. `/receiving/update-inventory-small`  
3. `/picking/sync-picking`  
4. `/picking/update-inventory`

---

## ⏱️ 実行頻度とコスト設計

| 頻度（cron） | 月間実行数 | 料金目安（USD） | 用途・コメント |
|-------------|------------|-----------------|----------------|
| `*/5 * * * *` | 約8,640回 | 約 $0.86/月     | ✅ 現在の推奨設定 |
| `* * * * *`   | 約43,200回 | 約 $4.32/月     | 即時性が重要な場合 |
| `0 * * * *`   | 約720回    | 無料枠内        | 非常に低頻度のバッチ向け |

> ※ 料金は東京リージョン、2025年時点の参考値  
> ※ 最新情報は [Cloud Scheduler 公式料金表](https://cloud.google.com/scheduler/pricing?hl=ja) を参照

---