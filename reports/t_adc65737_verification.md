# t_adc65737 検証レポート — complete_watchdog のコメント送信路修復

- タスク: t_adc65737（kensho-ai-team / assignee kensho-worker）
- コミット: a89e457
- 変更ファイル: `scripts/kensho-complete-watchdog.sh`（1ファイル / +30 -3）
- 発見元: t_3609e866 の実測（`logs/complete_watchdog_cron.log` 54 run / comment失敗 54/54）

## 1. 真因の特定（再現つき）

crontab 42行目は `*/30 * * * * bash .../kensho-complete-watchdog.sh --apply`。cron は最小環境
（`PATH=/usr/bin:/bin`）で起動するため `hermes` が解決できず、スクリプトの `hermes kanban comment` は
**exit 127（`hermes: not found`）で必ず失敗**していた。検出自体は正常（誤検知0件）だが通知が届かず運用効果ゼロ。

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin SHELL=/bin/sh /bin/sh -c 'hermes kanban --board kensho-ai-team comment t_adc65737 "test"'
/bin/sh: 1: hermes: not found
EXIT=127
```

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin SHELL=/bin/sh /bin/sh -c '/home/atushi/.hermes/hermes-agent/venv/bin/hermes kanban --board kensho-ai-team list | head -3'
Board: kensho-ai-team (1 other board — `hermes kanban boards list`)

✓ t_9e7b7456  done      kensho-revenue-worker  既存Apifyアクター73本のSEO・導線強化（icon/categories/version/README）
EXIT=0
```

## 2. 副次バグ（同時修正・t_adc65737）

台帳の重複防止は `grep -qE "^${TODAY}\t${tid}\t"` だったが、**GNU grep -E は `\t` をタブに展開しない**
（リテラル `t` として扱う）。実測では常に不一致で、dedup は一度も効いていなかった。
送信が全滅していた間は表面化しなかったが、送信を復旧させると**同一タスクへ30分ごとに再投稿されるスパム**になるため、
実タブ `$'\t'` へ是正した（候補検出ロジックは不変）。

```
$ TODAY=2026-09-24; TID=t_adc65737; L=logs/complete_watch_ledger.txt
$ grep -qE "^${TODAY}\t${TID}\t" "$L"; echo "old_pattern_match_exit=$?"
old_pattern_match_exit=1
$ grep -q "^${TODAY}"$'\t'"${TID}"$'\t' "$L"; echo "new_pattern_match_exit=$?"
new_pattern_match_exit=0
```

## 3. 検証（実測のみ）

### 3-1 受入条件1: cron 環境（非対話・最小PATH）でコメント送信が成功

旧ログを退避して新ログで実行（`env -i` で cron 相当の最小環境を再現）。

```
$ mv logs/complete_watchdog_cron.log logs/complete_watchdog_cron.log.pre-t_adc65737-fix
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin SHELL=/bin/sh LOGNAME=atushi /bin/sh -c 'bash /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-complete-watchdog.sh --apply >> /mnt/d/Project2/kensho/logs/complete_watchdog_cron.log 2>&1'
CRONLIKE_EXIT=0
$ cat logs/complete_watchdog_cron.log
kensho-complete-watchdog: board=kensho-ai-team stale_min=90git_days=2 candidates=1 remind=1
  complete-forgot: t_adc65737|git_dirty
  [ok] reminded t_adc65737 (git_dirty)
$ grep -c "comment failed" logs/complete_watchdog_cron.log
0
```

### 3-2 受入条件3: 実際に comment thread へ本文が入った（DB直読）

```
$ python3 -c "import sqlite3;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');print(c.execute(\"select id,author,substr(body,1,60),created_at from task_comments where task_id='t_adc65737'\").fetchall())"
1132 kensho-sweeps worker: 送信路診断テスト(1) ...
1133 tai [complete-forgot] 実装作業の痕跡(git_dirty)があるのに kanban_complete/block が未...
```

### 3-3 受入条件2: 失敗時に理由（rc/bin/stderr）がログに残る

```
$ HERMES_BIN=/bin/false bash scripts/kensho-complete-watchdog.sh --apply --ledger /tmp/cw_test_ledger.txt
kensho-complete-watchdog: board=kensho-ai-team stale_min=90git_days=2 candidates=1 remind=1
  complete-forgot: t_adc65737|git_dirty
  [err] comment failed: t_adc65737 rc=1 bin=/bin/false err=<no stderr>
EXIT=1
```

### 3-4 dedup（重複投稿しないこと）の回帰確認

```
$ B=$(wc -l < logs/complete_watchdog_cron.log); env -i ... /bin/sh -c '... kensho-complete-watchdog.sh --apply --verbose >> ...'; A=$(wc -l < logs/complete_watchdog_cron.log); echo "before=$B after=$A"
before=6 after=6
$ python3 -c "... count task_comments where task_id='t_adc65737'"
comments on t_adc65737 = 3
```

再実行でログ0行増・コメント0件増 = 同日重複リマインド抑止が機能。

## 4. 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"cron最小PATHで hermes 未解決→comment 54/54失敗の真因を再現特定し、絶対パス解決＋失敗理由ログ＋台帳dedupの\\tバグを t_adc65737 として修正・commit a89e457","what_went_well":["env -i で cron 環境を再現して真因を実測で確定","修正前に失敗→修正後に成功の Before/After を同一コマンドで提示","dedup の \\\\t 展開バグを grep 単体テストで証明(exit 1→0)"],"what_could_improve":["初回の --apply 検証でテスト対象タスクへ通知を1件実際に投稿してしまい、dedup不具合の検証で2件目が入った（結果的にバグ発見に寄与したが、テスト対象の選び方は改善余地）","loop_health.sh:401 にも同じ素の `hermes kanban comment` 呼出が残る（別タスク領域のため今回は未修正）"],"mistakes_or_risks":["cronログは追記式のため旧54件を退避して新ログで判定した（履歴は .pre-t_adc65737-fix に保持）","他ワークストリームの未コミット変更には触れず、自タスクの1ファイルのみコミット"],"learned":"cron(非対話・最小PATH)から hermes を呼ぶスクリプトは必ず絶対パスで解決すること。grep -E の \\\\t はタブにならない（$'\\t' を使う）。","confidence":9,"verification_evidence":"env -i最小PATH再現(exit127)/新ログcomment failed=0/DB comment id=1133実在/再実行0行増・0件増"}}
```

## verification_evidence

- 対象タスク: t_adc65737（本レポートは t_adc65737 の所有物）
- 受入条件1（cron環境でコメント送信成功）: `[ok] reminded t_adc65737 (git_dirty)` / CRONLIKE_EXIT=0 / `grep -c "comment failed"` = 0
- 受入条件2（失敗理由のログ記録）: `[err] comment failed: t_adc65737 rc=1 bin=/bin/false err=<no stderr>`
- 受入条件3（DBに本文が入る）: task_comments id=1133 が t_adc65737 に実在
- 副次バグ（dedup `\t` 未展開）: old_pattern_match_exit=1 → new_pattern_match_exit=0、再実行で0行増・0件増
- コミット: a89e457（`git log --oneline -1` で確認可能）
- 参照: t_3609e866（発見元QAカード）
