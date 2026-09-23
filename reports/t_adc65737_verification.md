# t_adc65737 検証レポート — complete_watchdog のコメント送信路修復

- タスク: t_adc65737（kensho-ai-team / assignee kensho-worker）
- コミット: a89e457（実装） / 4679c63（本レポート＋evidence.json）
- 変更ファイル: `scripts/kensho-complete-watchdog.sh`（1ファイル / +30 -3）
- 発見元: t_3609e866 の実測（`logs/complete_watchdog_cron.log` 54 run / comment失敗 54/54）

## verification_evidence

**before→after（成功指標）**

| 指標 | before | after |
|---|---|---|
| cron環境での comment 送信成功率 | 0/54 (0%) 全滅・exit 127 | 1/1 (100%)・exit 0 |
| 新ログの `comment failed` 件数 | 54 | 0 |
| 同一タスクへの同日重複リマインド | 毎回（dedup未機能） | 0件（2回目実行で0行増・0件増） |
| 失敗時の原因情報 | なし（`[err] comment failed: <id>` のみ） | rc / bin / stderr を記録 |

受入条件との対応:
1. cron 環境（非対話・最小PATH）でコメント送信1件以上成功 → `[ok] reminded t_adc65737 (git_dirty)`（経路は `hermes kanban comment` CLI を絶対パス解決）
2. 失敗時に失敗理由をログへ → `rc=1 bin=/bin/false err=<no stderr>`（下記 3-3）
3. 次回実行ログの `comment failed` = 0・comment thread に本文実在 → task_comments id=1133（下記 3-1 / 3-2）

### 1. 真因の特定（再現つき）

crontab 42行目は `*/30 * * * * bash .../kensho-complete-watchdog.sh --apply`。cron は最小環境
（`PATH=/usr/bin:/bin`）で起動するため `hermes` が解決できず、スクリプト内の `hermes kanban comment` は
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

### 2. 副次バグ（同時修正・t_adc65737）

台帳の重複防止は `grep -qE "^${TODAY}\t${tid}\t"` だったが、**GNU grep -E は `\t` をタブに展開しない**
（リテラル `t` 扱い）。実測で常に不一致＝dedup は一度も効いていなかった。送信が全滅していた間は表面化しなかったが、
送信を復旧させると**同一タスクへ30分ごとに再投稿されるスパム**になるため実タブ `$'\t'` へ是正した
（候補検出ロジック `stale_min=90` / `git_days=2` / 判定種別は不変）。

```
$ TODAY=2026-09-24; TID=t_adc65737; L=logs/complete_watch_ledger.txt
$ grep -qE "^${TODAY}\t${TID}\t" "$L"; echo "old_pattern_match_exit=$?"
old_pattern_match_exit=1
$ grep -q "^${TODAY}"$'\t'"${TID}"$'\t' "$L"; echo "new_pattern_match_exit=$?"
new_pattern_match_exit=0
```

### 3-1 受入条件1: cron 環境（最小PATH）でコメント送信が成功

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

### 3-4 dedup（重複投稿しない）の回帰確認

```
$ B=$(wc -l < logs/complete_watchdog_cron.log); env -i HOME=/home/atushi PATH=/usr/bin:/bin /bin/sh -c 'bash .../kensho-complete-watchdog.sh --apply --verbose >> .../complete_watchdog_cron.log 2>&1'; A=$(wc -l < logs/complete_watchdog_cron.log); echo "before=$B after=$A"
before=6 after=6
$ python3 -c "... count task_comments where task_id='t_adc65737'"
comments on t_adc65737 = 3
```

再実行でログ0行増・コメント0件増 = 同日重複リマインド抑止が機能。

### 4. 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"cron最小PATHで hermes 未解決→comment 54/54失敗の真因を再現特定し、絶対パス解決＋失敗理由ログ＋台帳dedupのタブ展開バグを t_adc65737 として修正・commit a89e457","what_went_well":["env -i で cron 環境を再現し真因を実測で確定","修正前失敗→修正後成功の Before/After を同一コマンドで提示","dedup の未マッチを grep 単体テストで証明(exit 1→0)"],"what_could_improve":["初回 --apply 検証で自分の t_adc65737 へ通知1件を実際に投稿し、dedup不具合検証で2件目が入った（バグ発見に寄与したがテスト対象の選び方は改善余地）","loop_health.sh:401 にも素の `hermes kanban comment` 呼出が残る（別タスク領域のため今回は未修正・申し送り）"],"mistakes_or_risks":["cronログは追記式のため旧54件を退避して新ログで判定（履歴は .pre-t_adc65737-fix に保持）","並行workstreamの未コミット11件には触れず、自タスクの1ファイルのみコミット"],"learned":"cron(非対話・最小PATH)から hermes を呼ぶスクリプトは必ず絶対パスで解決する。grep -E の \\t はタブにならない（$'\\t' を使う）。","confidence":9,"verification_evidence":"env -i最小PATH再現(exit127)/新ログcomment failed 54→0/DB comment id=1133実在/再実行0行増・0件増"}}
```

## 申し送り

- `scripts/loop_health.sh:401` も cron から `hermes kanban ... comment` を素の名前で呼んでいる（同じ根因の潜在バグ。park_action が none の間は無害）。次回の類似タスクで絶対パス化するか、共通ヘルパー化を推奨。
- t_3609e866 の申し送りどおり、復旧前の未送信リマインドを遡って送ることはしない（実装済み・対象は実行時点の候補のみ）。
