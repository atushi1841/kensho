# 検証証跡: t_7969ef3d — TCG価格データセット Gumroad出品 + 収益QA（ブロック）

## summary (t_7969ef3d)
- 親 t_3aa5365c からの委譲2項目（Gumroad出品・収益QA）を検証したところ、**GumroadセッションCookie失効** が確定（_gumroad_app_session exp=1789306033 < 現在 epoch ≈1790054078、約8.7日前失効）。人間による再エクスポート（EditThisCookie → Chrome で app.gumroad.com にログイン）が必須。
- 併せて **データ成熟ゲート未達**: accumulated obs=480 < 500+ 閾値（複数日ゲートのみPASS: 2026-09-21/22 の2日）。出品可能な静的データセット状態にまだ達していない。
- 収益QA（出品物URL・価格・説明文の確定検証）は**出品が不可能なため未実施**。Cookie再取得後に resume が必要。

## verification_evidence

$ date "+%Y-%m-%d %H:%M:%S %s"
> 2026-09-22 14:12:58 1790053978   (現在時刻・epoch)

$ grep _gumroad_app_session /mnt/d/Project2/gumroad-automation/gumroad_cookies.json
> "expirationDate": 1789306033.421445  (Cookie失効、exp < now)
> gumroad_publish.py: セッション有効期限約1ヶ月。失効時は人間の再export必須(スキル記載)

$ wc -l /mnt/d/Project2/kensho/data/tcg_dataset/accumulated.jsonl
> 480  (データ成熟ゲート 500+ obs 未達)

$ grep -oE '"collected_at"\s*:\s*"[0-9-]+' /mnt/d/Project2/kensho/data/tcg_dataset/accumulated.jsonl | cut -d'"' -f4 | cut -dT -f1 | sort -u
> 2026-09-21
> 2026-09-22   (複数日ゲート PASS)

## ブロック要因（kind=needs_input）
1. **GumroadセッションCookie失効（最重要）**: _gumroad_app_session の expirationDate=1789306033 は現在 epoch より約8.7日過去。出品自動化（gumroad_publish.py / Playwright Firefox + Cookie）には有効なセッションCookieが必須。
   → 人間に依頼: EditThisCookie 拡張で Chrome（app.gumroad.com ログイン済み）から Cookie を再エクスポートし /mnt/d/Project2/gumroad-automation/gumroad_cookies.json を更新。
2. **データ成熟ゲート未達**: accumulated obs=480 < 500+。蓄積cron（30 7 * * * / scripts/tcg_price_collect_cron.sh, RUNNING）による追加蓄積待ち。

## 出品準備（Cookie再取得後の実行前提、確定済み）
- タイトル: Japan Pokemon TCG Used-Price Dataset – Suruga-ya
- 価格案: 時系列 $20-50 / 単発スナップショットは無料サンプルで需要喚起
- 収益導線: 値動きクエリAPI（scripts/tcg_price_query.py / tcg_price_mcp.py）を $5-9/月 のクエリAPI（RapidAPI/Gumroadサブスク）へ接続
- 出品情報: bundle_info.json + 静的ZIP（data/tcg_dataset/ を同梱パッケージ化）
- 商品URL/価格/説明文の確定 → 収益QAの対象・未検証

## 次のアクション（人間 → dispatch 再開）
- Cookie 再エクスポート完了後、本タスクを unblock → resume し出品実行。データ成熟（500+ obs）も合わせて確認。
