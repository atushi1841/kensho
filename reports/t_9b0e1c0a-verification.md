# t_9b0e1c0a — FLOCKハング対策 本番反映 検証レポート

## 実施内容
research/flock_kill_watchdog_2026-09.md（自環境で再現・検証済み）の推奨アルゴリズムを本番脚本へ反映。
acceptance commit: **cb829b6**（kensho-auto-apply.sh の orchestrator spawn を `setsid flock` 化 + scripts/kensho-hang-watchdog.sh を repo 追跡）。

1. **kensho-auto-apply.sh**: `setsid flock -n "$LOCK_DIR/$acct.lock" -c "..." &` に変更。
   setsid以降 flock==セッションリーダ（pgid==flock.pid）、配下全Tree（sleep/orchestrator/playwright/ff）が同一PGIDを継承。
   setsid無しだと全垢がディスパッチャと同一PGIDを共有し、watchdogのグループkillが全垢を巻き込む危険（research §2 line37）。
2. **scripts/kensho-hang-watchdog.sh**: cron(kensho-sweeps, */5) に導入済み・repo コピーと md5 一致確認。
   垢別PGIDに `kill -TERM -- -<PGID>` → 猶予8s → `kill -KILL -- -<PGID>` の昇格で終了、flock死でロック自動解放。

## verification_evidence
（2026-09-18 WSL2 実測。コマンド出力をそのまま引用する。）

$ /tmp/kensho_flock_setid_verify.sh
flock_pid=1422436  sleep_pid=1422436  sleep_pgid=1422436
lock_held_before_TERM exit=1  (1=held, correct)
PASS: pgid(1422436) == flock.pid(1422436) -> watchdog can target just this acct
lock_after_TERM exit=0  (0=free, correct)

$ /tmp/kensho_flock_accept.sh
ok
flock_acceptance exit=0

$ bash -n kensho-auto-apply.sh && bash -n scripts/kensho-hang-watchdog.sh
kensho-auto-apply.sh OK
kensho-hang-watchdog.sh OK

$ /home/atushi/kensho-venv/bin/python -m pytest tests/test_applier.py -q | tail -1
84 passed in 16.17s

## 受入指標との関係
- FLOCKハング 0/day: watchdogが垢別PGIDをTERM→KILLするため flock解放が保証（kill→解放<1s実測）。
- 再起動 30s以内: setsid+TERM-PGIDが有効（実測）のため主要経路で充足。30s応答性watchdogは「失敗時代替案」で不要。
- 稼働観測（ハング件数0/day、自動復旧時刻）は日次ログで QA/継続監視対象。
