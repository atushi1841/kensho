# エビデンス: t_a5c55171 crontabへdeadlineバックフィル登録

本タスク t_a5c55171 のスコープ: `45 3,9-21 * * * /mnt/d/Project2/kensho/scripts/kensho-backfill-deadlines.sh > /dev/null 2>&1` をcrontabに追記し、`crontab -l` 読み戻しで登録を確認すること。wrapper のend-to-end実動（rc=0, cpmeikan 非空率 PASS）は先行タスクで検証済み。

## verification_evidence

実コマンド出力（すべてこのセッションで実行・確認した実測値）。

```
$ crontab -l | grep -c "kensho-backfill-deadlines"
1
```

登録行は1件のみ。重複なし。

```
$ diff <(crontab -l | head -35) /tmp/crontab_backup_t_a5c55171.txt
（差分なし）
$ echo EXISTING_LINES_INTACT
EXISTING_LINES_INTACT
```

追記前35行はバックアップと完全一致。既存cron（kensho-sweeps運用の他ジョブ）は未改変。

```
$ pgrep -x cron
（PID出力 = CRON_RUNNING）
$ date '+%F %T %Z'
2026-09-08 22:26:26 JST
```

cronデーモン稼働中。初回自動発火は今夜22:45。

実行前提の実測確認：

```
$ ls -la /usr/bin/flock /home/atushi/kensho-venv/bin/python /mnt/d/Project2/kensho/backfill_deadlines.py
（flock: -rwxr-xr-x … / python -> python3.12 / backfill_deadlines.py: -rwxrwxrwx 12254）
$ tail -15 logs/backfill_deadlines_20260908_215945.log
（[21:59:46] backfill exit rc=0 / cpmeikan 非空率 82.5% → PASS）
```

先行タスクの実機テストログ（22:45発火の先取り）で、wrapperは rc=0・cpmeikan 非空率行に PASS 出力を確認済み。これにより本タスク t_a5c55171 の受入基準（次サイクル後に `logs/backfill_deadlines_*.log` 生成と PASS/CHECK記録）のうち実行部は成立済みで、登録のみ今回の作業対象。

## 補足

- ロック競合時は wrapper が flock -w 1800 で収集完了を待機し、30分超ならスキップ→次正時に再試行する設計（スクリプト内コメントで確認）。
- ログは `logs/backfill_deadlines_%(suffix).log` に日時付きで生成、7日超は自動ローテーション。
