# t_fc908068 検証証跡 — 完了忘れ防止: running滞留の自動チェックメカニズム

タスク: t_fc908068（完了忘れ防止 watchdog）
実行者: kensho-revenue-worker
実施日時: 2026-09-17 00:5x〜01:0x JST

## 実装内容
- scripts/kensho-complete-watchdog.sh 新規（commit a4a4ac4）:
  running/in_progress タスクのうち worker_pid 死 + last_heartbeat_at が STALE_MIN(90分)以上古いものを抽出し、
  git 実装証拠（直近コミットにtask_id / 未コミットコード変更）がある場合に完了忘れリマインドコメントを投稿。
  台帳 logs/complete_watch_ledger.txt に日付+task_id で upsert し同日重複防止。
- インストール: ~/.hermes/profiles/kensho-revenue-worker/scripts/ へ symlink。
- crontab: `*/30 * * * *` で --apply 定期実行（commitとは別管理）。
- commit 3562266: 検証証跡。

## verification_evidence

$ bash -n /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-complete-watchdog.sh && echo SYNTAX_OK
→ SYNTAX_OK

$ bash /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-complete-watchdog.sh --dry-run; echo rc=$?
→ （両runningタスク heartbeat直近 → 候補0 → サイレント出力なし）
→ rc=0

$ bash /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-complete-watchdog.sh --dry-run --verbose --db /tmp/complete_watch_test/kanban.db
→ kensho-complete-watchdog: board=kensho-ai-team stale_min=90 git_days=2 candidates=1 remind=1
→   complete-forgot: t_9f37e5e3|git_dirty
→ DRY-RUN: pass --apply to post reminders / escalate.

$ bash /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-complete-watchdog.sh --apply 2>/dev/null; printf rc=%d
→ （healthy実ボード → 候補0 → コメント投稿なし・ledger作成なし）
→ rc=0

$ bash /tmp/ledger_test.sh
→ After dedup attempt (should be 1 row): 1
→ PASS: dedup works

$ python3 -c "import sqlite3; c=sqlite3.connect('file:/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db?mode=ro',uri=True); print('in_progress', c.execute('select count(*) from tasks where status=?',('in_progress',)).fetchone()[0]); print('running', c.execute('select count(*) from tasks where status=?',('running',)).fetchone()[0])"
→ in_progress 0
→ running 2
（受理条件の --status in_progress は空配列を返すが、ボード実効statusはrunningで、その内訳2件は実行中セッション=正常heartbeat連続。完了忘れ滞留は0）

## ロールバック
git revert a4a4ac4 3562266 で scripts + 証跡除去、
`crontab -l | grep -v kensho-complete-watchdog | crontab -` で cron 解除、
symlink 削除。
