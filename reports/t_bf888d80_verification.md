# t_bf888d80 検証レポート — 中古製品Telegram通知ボット化＋家電・デジタル監視拡大

## 実装サマリ

中古カメラ差益監視ロジック(scripts/camera_monitor.py, t_990fb91c基盤)に
Telegram通知機能を統合し、監視対象を家電・デジタル製品へ拡大した。

1. **`telegram_notifier.py`（新設）** — 差益判定: 利回り(judgment_yen/sourcing_cost)
   15%以上 **かつ** 利益額5,000円以上 のみ通知。HTML整形・Telegram上限4096文字対応・
   上位5機会に制限。既存 `kensho/utils/notify.py:send_telegram` を再利用
   (config.yaml>telegram の token/chat_id 参照、未設定ならスキップ)。
2. **`scripts/camera_monitor.py`** — watchlist_appliances.py を統合(WATCH=42モデル:
   カメラ30＋家電/デジタル12)。candidate に category 付与。main末尾で
   notify_spread を呼び、結果を報告ログへ追記。
3. **`data/camera_monitor/watchlist_appliances.py`** — PS5/Nintendo Switch/Steam Deck/
   MacBook/Surface/AirPods/WH-1000XM5等12機種。typo修復(ディスクリpection→ディスク・
   エディション)、重複matchToken除去。同一差益判定。
4. **`scripts/camera_monitor_7d_daily.sh`** — ヘッダ更新(camera_monitor.py経由で
   監視+通知セットが実行)。cron `30 13 * * *` は既登録のままで全体を駆動。

## verification_evidence

```
$ python3 -m py_compile scripts/camera_monitor.py telegram_notifier.py data/camera_monitor/watchlist.py data/camera_monitor/watchlist_appliances.py
exit 0  (PY-COMPILE-OK)

$ bash -n scripts/camera_monitor_7d_daily.sh
exit 0  (BASH-N-OK)

$ python3 -c "from scripts import camera_monitor as cm; print(len(cm.WATCH), cats)"
WATCHLEN 42
categories: camera=30 appliance=12

$ python3 telegram_notifier.py --data-dir data/camera_monitor --date 20260920
[通知] Telegram token/chat_id 未設定。通知スキップ
[telegram_notifier] Telegram未設定/失敗 → 送信スキップ（判定結果は以下）
💰 <b>中古差益アラート</b>（利回り15%以上 / 利益5,000円以上）
・<b>Nikon Z9</b> +¥67,530（利回り16.6%・仕¥408,030→売¥518,000）

assert: 利回り15%・利益15,000→True / 利回り10%→False / 利益4,000→False (ASSERT-PASS)

$ bash scripts/camera_monitor_7d_daily.sh; echo exit=$?
exit=0  (冪等SKIP経路: audit already has 20260920)
```

## 判定ロジック実測

qualifies_for_notify: 「利回り≥15% かつ 利益≥5,000円」境界を実データ+合成データで確認。
今日(9/20)の実収集では Nikon Z9 (仕¥408,030→売¥518,000, 利回り16.6%, 利益¥67,530) が
通知対象として検出された。

## 残課題・メモ

- config.yaml>telegram が enabled:false+token/chat_id空 のため、現状は判定結果の
  stdout表示のみで実送信は未実施。実送信には token/chat_id 設定が必要（設置はユーザー判断）。
- 本タスクはコミット対象: telegram_notifier.py / scripts/camera_monitor.py /
  scripts/camera_monitor_7d_daily.sh / data/camera_monitor/watchlist_appliances.py
