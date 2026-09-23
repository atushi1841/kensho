# Critic観察レポート 2026-09-24

対象: 前日 2026-09-23
- KENKAKU平均取得: 17.5件（4セッション）
- ConnectTimeout: 9件/day
- [源別ConnectTimeout] KENKAKU=9 KCLUB=0 KEMA=0 CPMK=0（計9件）
  - KENKAKU: 9件
  - KCLUB: 0件
  - KEMA: 0件
  - CPMK: 0件
- apply成功率: 95.1%（成功704/エラー36）

## 5. 新たな問題点（critic判定 2026-09-24 00:2x JST）

### 【高・要ユーザーGO】BOT「正規性」シグナルが6日連続で検出
- 実測: `~/.hermes/profiles/kensho-sweeps/cron/output/eb7bc8c022e2/` の日次監査で
  9/17=1件, 9/18=1件, 9/19=1件, 9/20=2件, 9/21=2件, 9/22=2件（kudou 5日連続, TankanNotes 2日, zin 4日）
- 例: 9/22 kudou 初動stdev 10.6分(<30)・直近6日 初動8時台中心 / TankanNotes 初動stdev 13.6分・件数CV0.02(<0.15)
- 原因判定: t_ed8baffa(9/16 planB適用, 92ca4b8)のスタガーは **起動層 0〜9分** のみ。
  初動時刻の日跨ぎstdevは構造的に <30分 に収まり、監査の閾値を永続的に踏む。
- 既存カード有無: 「ジッタ/初動/規則性」で検索 → 起票済みなし（t_865a35e3/t_ed8baffa=9/16対処は別層）
- 対応案（応募スケジュール＝禁止領域のため**ユーザーGO必須**）:
  A) 日次シード付きスタガー幅拡大（0〜9分 → 0〜45分、seed=日付+垢）
  B) 初回バッチ時刻の曜日ローテ（8時台/9時台/10時台）
  制約: no_action_window 00:00-07:00 と 22:47終了を割らない。
- 成功指標: 翌7日間の「正規性」検出が kudou/TankanNotes ともに0件
- 検証: `/home/atushi/kensho-venv/bin/python scripts/audit_bot_safety.py --help` 系の日次実行で
  「正規性」行が出力されないこと（`grep -c 正規性 <日次出力>` => 0）

### 【中】BOT監査ジョブが毎日 last_status=error 表示
- `kensho-daily-bot-safety-audit`(eb7bc8c022e2) はシグナル検出時に exit 1 する設計のため、
  正常動作でも「error」と表示され、真の障害と区別できない（9/17以降毎日）。
- 対策: ラッパー `kensho-daily-bot-audit.sh` で検出時も exit 0 にし、本文で通知する。

### 【解決】stall-check 二重登録
- `kensho-apply-stall-check` は 8b591344b267(no_agent, enabled) と 239b27112e9e(agent, **enabled=False**) に
  分離済みで実害なし。QAからの委譲分はクローズ。

### 【完了】t_fa046d3a の滞留解消（critic実測検証でdone化）
- goal_mode judge の BadRequestError で34.5h ready滞留 → 独立検証
  （`git merge-base --is-ancestor f906e3a origin/main` => true / `pytest tests/test_self_heal.py` => 18 passed /
  reports/t_fa046d3a_verification.md 実在）のうえ done化。子QA 2件(t_3609e866/t_66c14eb4)を解放。
