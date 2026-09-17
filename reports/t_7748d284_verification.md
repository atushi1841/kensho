# t_7748d284 検証レポート — ゾンビタスク自動検出・自動unblock+再割当

対象: `scripts/kensho-zombie-watchdog.sh`（新規・canonical）+ profileデプロイ版
`~/.hermes/profiles/kensho-sweeps/scripts/`、`loop_health.sh`（zombie_task_count）
日時: 2026-09-17 JST
責務: ボード監視検知層のみの追加。応募パイプライン・応募ロジック一切不変更。

## 背景
worker が rc=0 で正常終了しても kanban_complete/kanban_block を呼び忘れると、
dispatcher は protocol violation として回路遮断（上限3回）→ タスクは blocked で
永久滞留する（問題 t_9f37e5e3 実例: 22時間滞留）。これを定期ウォッチドッグが検出
し、自動 unblock（blocked→ready）で dispatcher に再割当させる検知層を追加した。

## 検証

### A) watchdog dry-run が真のゾンビだけを検出する
$ cd /mnt/d/Project2/kensho && bash scripts/kensho-zombie-watchdog.sh --dry-run
出力: zombie-watchdog: board=kensho-ai-team max_unblocks=2 zombie=1 (escalate=0)
  t_9f37e5e3 unblocks=0 age=22h assignee=kensho-worker
判定: blocked + last_failure_error LIKE '%protocol violation%' のタスクのみを狙い撃ち。
iteration-budget 遮断タスク t_06fdd792（別原因）は誤検出されない。✅

### B) --apply 実効: ゾンビを unblock → ready 再割当
$ bash scripts/kensho-zombie-watchdog.sh --apply
出力: auto_unblocked=1 failed=0 / [OK] t_9f37e5e3
事後DB確認: t_9f37e5e3 status=ready / consecutive_failures=0 / last_failure_error=NULL
/ task_events に unblocked 刻印 / 台帳 state/zombie_ledger.json unblocks=1。✅

### C) loop_health score に zombie_task_count（1件 -10）
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --dry-run --no-park --tasks '[]'
出力: score=90 zombie=1（真ゾンビ1件 → 100 から -10）。
override 系（LOOPHEALTH_ZOMBIE_COUNT=0/2）は tests/test_zombie_watchdog.py で決定論検証。✅

### D) pytest 回帰（新規 + 既存）
$ python -m pytest tests/test_zombie_watchdog.py tests/test_loop_health_business.py tests/test_loop_health.py -q
結果: 9 passed（新規4本: dry-run検出がpvゾンビのみ/非pv除外 + score override 0/2 減点）
既存 loop_health top_task/business gate は未回帰。✅

### E) 冪等性 + cron drift
$ bash scripts/kensho-zombie-watchdog.sh --apply   # 2回目（t_9f37e5e3は既にready）
出力: （0検出 = 空stdout・サイレント規約）
$ python3 scripts/kensho_script_drift_check.py --json
出力: {"ok": true, "drift": 0, "missing": 0, "fails": []}

## 判定
- ゾンビ検出: 真の protocol-violation blocked のみ（iteration-budget別原因は除外）✅
- 自動unblock+再割当: t_9f37e5e3 を ready 化・unblocked 刻印・台帳記録 ✅
- zombie_task_count 追加: 実ボード score 100→90、override で決定論検証 ✅
- pytest 回帰 9本パス / cron drift 0 / bash -n OK ✅

## 備考
- ループガード: ZOMBIE_MAX_UNBLOCKS=2 を超えると自動unblockせず escalation として
  残す（block→unblock→block churn 抑制）。台帳は complete で reset する拡張余地あり。
- 本タスクは検知層のみの変更（応募ロジック非改修）のため自動 GO 対象。
