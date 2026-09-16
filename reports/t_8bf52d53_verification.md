# t_8bf52d53 検証証跡 — critic v164 当選率源別自動分析

## verification_evidence

実測コマンドと出力のみ記載（推測なし）。

$ .venv/bin/python -m pytest tests/test_winrate_analysis.py -q
........ [100%]
8 passed in 1.64s

$ .venv/bin/python scripts/kensho_winrate_analysis.py --week 2026W38
winrate 2026W38: wins=15 matched=7 unmatched_rate=53.3% sources=8 → /mnt/d/Project2/kensho/reports/winrate-2026W38.md

$ bash /home/atushi/.hermes/scripts/kensho-winrate-weekly.sh
winrate 2026W37: wins=15 matched=7 unmatched_rate=53.3% sources=8 → /mnt/d/Project2/kensho/reports/winrate-2026W37.md
（rc=0 / reports/winrate-2026W37.md 生成実測）

$ hermes cron create --name kensho-winrate-weekly --no-agent --script kensho-winrate-weekly.sh --deliver telegram:8510166694 "0 6 * * 1"
Name: kensho-winrate-weekly
  Schedule: 0 6 * * 1
  Script: kensho-winrate-weekly.sh
  Mode: no-agent (script stdout delivered directly)
  Next run: 2026-09-21T06:00:00+09:00

$ .venv/bin/python -m pytest -q
3 failed, 646 passed, 5 skipped in 124.17s
→ 失敗3件は tests/test_regression_gates.py のみ。git stash で本変更を退避した状態でも同一3件失敗を確認（=既存failure・本タスク無関係。t_c6b4e3ed教訓「9/18窓rollで自然解消・不干渉」）

## 受け入れ条件対応
- 源別当選率が4源分以上: **8源**数値出力（knshow 801/5=0.62%、kenshouclub 367/0、twscrape 265/2=0.75%、kema 174/0、ken-kaku 128/0、kensho-everyday 24/0、chancecom 20/0、cpmeikan 17/0）
- 突合マッチ件数>0: 7件、unmatched率 53.3% をレポートに明記
- 検証コマンド `python3 scripts/kensho_winrate_analysis.py --week 2026W38 && ls reports/winrate-2026W38.md` → 両方成功
- 週次cron登録済み（kensho-winrate-weekly、次回 2026-09-21 06:00 JST、no_agent、Telegram配信）
- card前提の apply_logs テーブルは data/actions.db が0バイトで不在 → 本文「失敗時代替案」どおり tweet_url/handle照合にフォールバック済み（blocked相当の「突合キー再設計」は不要。マッチ7件>0のため）

## 変更ファイル
- scripts/kensho_winrate_analysis.py（新規）
- tests/test_winrate_analysis.py（新規・8テスト）
- reports/winrate-2026W38.md / reports/winrate-2026W37.md（実行成果物）
- reports/revenue-proposals/2026-09-16-revenue-worker-t_8bf52d53.md（実施記録+Reflexion）
- ~/.hermes/scripts/kensho-winrate-weekly.sh（cronラッパー・プロファイル配下）
