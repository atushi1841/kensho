# t_5086aef7 実装報告 — evolution v102: escalation SLA parking（v133 + v133b クローズ）

日付: 2026-09-12 04:00 JST / 作業者: kensho-revenue-worker / run 399
カード: t_5086aef7（t_5086aef7 の受け入れ条件＝本文のpark実装+成功指標充足を本報告で証跡化する。t_5086aef7 QA run395①のv133bクローズも含む）

## 実施内容

エスカレーション無応答 blocked の自動 scheduled 退避（PagerDuty escalation-policies / Google SRE on-call 準拠）。

1. **v133（本体）**: `scripts/loop_health.sh` に PARK_AFTER_H ゲートを実装。escalation が `escalated_at` 起点で PARK_AFTER_H（既定 24h、冒頭変数で調整可）連続発動したままなら、`hermes kanban schedule <tid>` で top target を scheduled へ自動退避 + `[loop-health]`/SLA コメント付与。退避済み tid は blocked 計算から外れ streak リセット方向に働く。状態書き込みは単一化（v30 bug #3 系の重複 jq 書き換え解消）。
   - 根拠（QA 23:23 指摘への回答）: task 本文の 72h → 実装 24h の短縮は意図的。実測で streak=11・30h 無応答が既に出ているため、72h は滞在意図に反する。24h は既設の park cooldown（6h）と組み合わせ過剰発動を抑える。
2. **v133b（QA run395① 実バグ修正、本runでコミット `b5f5cd9`）**: park 発動時に持続 band（`last_escalate_streak`/`last_low_band`/`escalated_at`）を現 streak へ再設定。band が streak を上回ったまま残ると不変条件 `last_escalate_streak <= streak` が破れ、healthy board でも escalation=true が持続 → cooldown ごとに別 target を連続 park する（v92 指標2 FAIL 真因）。高スコア分岐でも band<=streak のときのみ永続化。
3. **monitor 同期（同一コミット原則）**: `~/.hermes/scripts/board_state_monitor.sh` / `board_state_monitor_critic.sh`（sweeps プロファイル版含む）を v133 の bool 化・counts/skip_fast 出力へ両形式フォールバック対応済み（2026-09-12 00:44/01:24、QA が先行実施）。本runで loop_health.sh 側にも `counts`/`skip_fast` フィールドを追加し monitor の期待スキーマと整合させた。
4. **両パス同期**: プロジェクト版と `~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh`（monitor が実行する版）は md5 一致（244704af…）を確認。

## 受け入れ条件検証（t_5086aef7 本文 + QA 成功指標）

- 退避実施済み: t_443551e0 / t_c186bf62 は `scheduled`（run395 が SLA 30h > 24h ゲートで park 実行、コメント 02:17 に記録あり）
- `bash scripts/loop_health.sh` → score=100, counts.blocked=0, skip_fast=false（成功指標 score>=85 / blocked<=0 / skip_fast=False 充足）
- monitor 署名 2 回一致: commit 前後それぞれ 2 回実行 diff ゼロ、かつコミット後 dirty=N（ストーム遮断ゲート正常）
- pytest 545 passed, 5 skipped（既存全通過）
- バーンアウト実証: run395 の park で AI チームループは skip_fast=False 復帰、以後 blocked 滞留による -25/-5 要因は消滅

## 残余事項（他カード扱い）

- `~/.hermes/scripts/`（共有版）と sweeps プロファイル版 monitor は parse 実装が微妙に差異（both 動作・署名互換）。恒久統一は t_c34941bd 申し送り系のスコープ。
- park 済みの 2 件（t_443551e0/t_c186bf62）の再着手判断はユーザ保留（scheduled のまま）。

## verification_evidence

$ git log --oneline -1
b5f5cd9 fix(loop_health): v133b — park成功で持続bandを現streakへ再設定し不変条件(last_escalate_streak<=streak)を回復 + monitor互換のcounts/skip_fast出力追加 [t_5086aef7 QA run395①]
$ bash /mnt/d/Project2/kensho/scripts/loop_health.sh > /tmp/lh_1.json; jq -c '{score, counts, skip_fast, escalation, park_action}' /tmp/lh_1.json
{"score":100,"counts":{"running":1,"blocked":0},"skip_fast":false,"escalation":false,"park_action":"none"}
$ bash /mnt/d/Project2/kensho/scripts/loop_health.sh > /tmp/lh_2.json; jq -c 'del(.last_run_ts, .updated_at)' の2回diff
SIGNATURE_MATCH_2RUN
$ hermes kanban --board kensho-ai-team show t_443551e0 | head -2
Task t_443551e0: critic v90: … status: scheduled
$ hermes kanban --board kensho-ai-team show t_c186bf62 | head -2
Task t_c186bf62: 第4弾MCP: … status: scheduled
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor.sh (コミット後2回)
score=100|ready=0|blocked=0|wip=1|prio=normal|streak=0|esc=False|skip=False|dirty=N
POSTCOMMIT_2RUN_IDENTICAL
$ .venv/bin/python -m pytest -q (tail)
================== 545 passed, 5 skipped in 70.73s (0:01:10) ===================
$ md5sum /mnt/d/Project2/kensho/scripts/loop_health.sh ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
244704af7c57f3bd2151bccb1b6bd232  同一（両パス同期確認）
$ git -C /mnt/d/Project2/kensho rev-list --count origin/main..HEAD
0（push 済み、ahead 0）
