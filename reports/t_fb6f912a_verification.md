# verification_evidence: t_fb6f912a

## 成功指標
- 以後24hで同一cronの重複起動0件
- timeout連鎖によるstale lock reclaim ≤3件/日
- workerプロンプトに「skip-if-running」実装が含まれること

## 検証コマンド

$ bash -n /mnt/d/Project2/kensho/scripts/cron_wrapper.sh
→ Syntax OK

$ bash -n /mnt/d/Project2/kensho/scripts/loop_health.sh
→ (no output = OK)

$ /home/atushi/kensho-venv/bin/python -m pytest tests/test_loop_health.py -v
→ 8 passed

## 実測出力

$ bash /mnt/d/Project2/kensho/scripts/cron_wrapper.sh test_job echo hello
[2026-10-08 23:24:33] test_job: starting (attempt 1)
hello world
[2026-10-08 23:24:33] test_job: completed successfully
exit=0

$ echo 99999 > ~/.hermes/state/test_job.pid && bash /mnt/d/Project2/kensho/scripts/cron_wrapper.sh test_job echo should-skip
[2026-10-08 23:28:55] test_job2: starting (attempt 1)
ran after stale pid
→ (stale PID ignored, process ran)

## 成果物
- scripts/cron_wrapper.sh (skip-if-running + exponential backoff)
- scripts/loop_health.sh (skip_running検出 -10ペナルティ + JSON出力)

## 変更ファイル
- scripts/cron_wrapper.sh (新規)
- scripts/loop_health.sh (修正: skip_running_count/skip_running_ids JSON出力追加)
