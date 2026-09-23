# t_5af1b5d8 — AIチーム健康度ゲート loop_health.sh の単一ソース化 + bare `hermes` 絶対パス化

- カード: t_5af1b5d8（board kensho-ai-team / assignee kensho-worker）
- 親カード: t_e67d5550（timeout-watch の同型修正。本カードはその申し送り#2 = 同型バグ掃討の独立カード化）
- 対象実体: `/mnt/d/Project2/kensho/scripts/loop_health.sh`
  （profile の v139 実物を **1バイトも変えずに移設**。profile 経路は同ファイルへの symlink へ切替）
- 実行実体（cron が叩くパス）: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh`
  → `/mnt/d/Project2/kensho/scripts/loop_health.sh`（v141）
- 変更規模: repo の旧コピー(v137, 21268B)比 +183 / -13。うち v139 実物の取り込みが +147 行で、
  本カード t_5af1b5d8 が書いたコードは「HERMES_BIN 解決ブロック」＋「bare hermes 6箇所の置換」＋「ヘッダ v141 注記」のみ
- 検証ログ実物: `/tmp/t_5af1b5d8/logs/`（before_run.log / after_run.log / destructive_run.log / a7_run.log / step2.log）
- 判定ロジック・閾値・score 計算・advice 文言・JSON スキーマは一切不変（置換のみ）
- 本カード t_5af1b5d8 が触ったファイルは上記1本＋証跡2点（本レポートと evidence.json）のみ

## verification_evidence

### 0. 成功指標（before → after / 全て実測）

| 指標 | before | after |
|---|---|---|
| 最小PATH実行の running / blocked | 0 / 0（無音縮退） | 3 / 1（通常PATH実行と一致） |
| 最小PATH実行 vs 通常実行の JSON diff（`jq -S` 正規化） | 36行 | **0行** |
| loop_health.sh 内の bare `hermes` 実行呼出 | 6箇所 | **0箇所**（`"$HERMES_BIN"` 経由。残りはコメント/メッセージ文のみ） |
| CLI 解決不能時の挙動（本番入力なし） | stderr 無出力・rc=0・running=0 に縮退 | rc=**127** ＋ PATH と HERMES_VENV_BIN を stderr に記録 |
| auto-park 破壊的経路（comment/schedule）の実DB書き込み | —（実行に到達する前に hermes が落ちる） | **0**（argv 記録シムで捕捉のみ。DB fingerprint 6項目すべて delta 0） |
| 移設の byte 同一性 | profile 実物=28866B / sha256 5755526e... | profile symlink 先=repo 実体=同 28866B / 同 sha256（1バイトも不変） |

補足: before の 36行差は `blocked`(0→1) / `running`(0→2) / `escalation_target`(null→実カード) /
`top_task`(none→最古running) の4系統で、いずれも「健康度の入力そのものが空」に起因する無音縮退。

### 1. 前提の再現（cron 最小PATHでは `hermes` が解決できない）

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin bash /tmp/t_5af1b5d8/bin/probe.sh
hermes: NOT FOUND
sqlite3: NOT FOUND
jq: /usr/bin/jq
python3: /usr/bin/python3
PATH=/usr/bin:/bin
```

cron は `PATH=/usr/bin:/bin` で起動するため `~/.hermes/hermes-agent/venv/bin` が PATH に無く、
旧コードの bare `hermes` 呼出は全て空を返していた（= 健康度ゲートが「常に健康」に見える）。

### 2. BEFORE（profile v139 実物・未修正のまま最小PATHで実走）

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/before_min.json --no-park
rc=0
{"score":100,"running":0,"blocked":0,"alert":"OK","business_ok":true,"business_done":0}
```

一方、通常 PATH（`hermes` 解決可）では正値が出る。同一入力に対する before の差は 36 行。

```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/before_norm.json --no-park
{"score":100,"running":2,"blocked":1,"alert":"OK","business_ok":true,"business_done":0}
```

```
$ diff /tmp/t_5af1b5d8/logs/before_min.sorted.json /tmp/t_5af1b5d8/logs/before_norm.sorted.json | grep -c '^[<>]'
36
```

`running=0 / blocked=0 / escalation_target=null` になるため `advice.priority=blocked_triage` が二度と出ず、
worker/qa/evolution のプロンプト分岐（priority 依存）と auto-park 通報路が同時に沈黙する。

### 3. 移設と symlink 化（sha256 一致の証跡）

```
$ sha256sum /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh /mnt/d/Project2/kensho/scripts/loop_health.sh
5755526e48e00200a91d6615e64676d791cfd1975c77249cdf9f9da738fc0690  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
5755526e48e00200a91d6615e64676d791cfd1975c77249cdf9f9da738fc0690  /mnt/d/Project2/kensho/scripts/loop_health.sh
```

```
$ wc -c /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh /mnt/d/Project2/kensho/scripts/loop_health.sh /tmp/t_5af1b5d8/backup/loop_health.sh.v139.orig
28866 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
28866 /mnt/d/Project2/kensho/scripts/loop_health.sh
28866 /tmp/t_5af1b5d8/backup/loop_health.sh.v139.orig
```

```
$ ls -la /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
lrwxrwxrwx 1 atushi atushi 45 Sep 24 07:46 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh -> /mnt/d/Project2/kensho/scripts/loop_health.sh
```

レイアウトは親カード t_e67d5550（timeout-watch / complete-watchdog）と同一の単一ソース化。
元実体は `/tmp/t_5af1b5d8/backup/loop_health.sh.v139.orig` に保全済み。

### 4. AFTER-1（最小PATH＝本番経路で実走。修正の主目的）

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin bash /mnt/d/Project2/kensho/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/after_min.json --no-park
rc=0
{"score":100,"running":3,"blocked":1,"alert":"OK","escalation_target":"t_c0e0563d"}
```

```
$ /home/atushi/.hermes/hermes-agent/venv/bin/hermes kanban --board kensho-ai-team list --json --status blocked | jq 'length'
1
$ /home/atushi/.hermes/hermes-agent/venv/bin/hermes kanban --board kensho-ai-team list --json --status running | jq 'length'
3
```

最小PATHでの `running/blocked` が実ボードの実測値（3 / 1）と一致することを確認。

### 5. AFTER-2（受入条件3: 無回帰の数値証明 = diff 0行）

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin bash /mnt/d/Project2/kensho/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/after_min.json --no-park | jq -S . > /tmp/t_5af1b5d8/logs/after_min.sorted.json
$ bash /mnt/d/Project2/kensho/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/after_norm.json --no-park | jq -S . > /tmp/t_5af1b5d8/logs/after_norm.sorted.json
$ diff /tmp/t_5af1b5d8/logs/after_min.sorted.json /tmp/t_5af1b5d8/logs/after_norm.sorted.json | grep -c '^[<>]'
0
```

before=36行 → after=**0行**。さらにボード churn の影響を排除するため、CLI 出力を凍結フィクスチャに
固定した比較（最小PATHは HERMES_VENV_BIN 経由 / 通常PATHは HERMES_BIN 固定）でも 0 行。

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin HERMES_VENV_BIN=/tmp/t_5af1b5d8/bin bash /mnt/d/Project2/kensho/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/a5b_min.json --no-park | jq -S . > /tmp/t_5af1b5d8/logs/a5b_min.sorted.json
$ HERMES_BIN=/tmp/t_5af1b5d8/bin/hermes bash /mnt/d/Project2/kensho/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/a5b_norm.json --no-park | jq -S . > /tmp/t_5af1b5d8/logs/a5b_norm.sorted.json
$ diff /tmp/t_5af1b5d8/logs/a5b_min.sorted.json /tmp/t_5af1b5d8/logs/a5b_norm.sorted.json | grep -c '^[<>]'
0
```

### 6. AFTER-3（受入条件4: 破壊的経路は argv シムで捕捉のみ・実DB書き込みゼロ）

`HERMES_BIN` を argv 記録シム（`/tmp/t_5af1b5d8/bin/hermes`）に差し替え、park gate が開く入力
（escalation 25h 継続 + score 5）で **DRY_RUN を切って**実走した。シムは `comment` / `schedule` を
受け取るだけで DB に触れない（本体は記録して ACK を返すのみ）。

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin HERMES_BIN=/tmp/t_5af1b5d8/bin/hermes ... bash /mnt/d/Project2/kensho/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/a7_seed.json
a7 rc=0
{"score":5,"running":5,"blocked":2,"alert":"ALERT","escalation":true,"escalation_target":"<top_task>","park_action":"parked","escalated_at":null,"escalation_age_h":25}

$ cat /tmp/t_5af1b5d8/logs/shim_a7.log
1790204742	kanban --board kensho-ai-team list --json --status blocked
1790204742	kanban --board kensho-ai-team list --json --status running
1790204743	kanban --board kensho-ai-team show <top_task> --json
1790204743	kanban --board kensho-ai-team comment <top_task> <[loop-health] marker body redacted>
1790204743	kanban --board kensho-ai-team schedule <top_task> <[loop-health] marker redacted>
```

schedule 側の戻り値は成功（`{"ok":true,"status":"scheduled"}`）で `park_action=parked` まで到達。
つまり **本番入力では comment + schedule が実際に発火する経路**であり、
修正前はその直前（blocked/running 取得）で無音縮退していたことが数値で裏づけられた。

実 DB（`~/.hermes/kanban/boards/kensho-ai-team/kanban.db`）は前後で 1 行も変化していない。

```
$ python3 /tmp/t_5af1b5d8/db_fingerprint.py   # A7 実行の直前 / 直後
max_comment_rowid      before=1151     after=1151     delta=0
task_comments          before=1151     after=1151     delta=0
tasks_scheduled        before=8        after=8        delta=0
tasks_status_digest    before=f7b3858f... after=f7b3858f... delta=0
tasks_status_rows      before=729      after=729      delta=0
tasks_total            before=729      after=729      delta=0
```

```
$ python3 - <<'PY'  (実DBに [loop-health] マーカーが増えていないことの確認)
loop_health_comments_last_15min = 0
PY
```

### 7. AFTER-4（受入条件2: 解決不能時は PATH と HERMES_VENV_BIN を stderr に残して非0終了）

```
$ env -i HOME=/home/atushi PATH=/usr/bin:/bin HERMES_VENV_BIN=/nonexistent-venv-dir bash /mnt/d/Project2/kensho/scripts/loop_health.sh --state /tmp/t_5af1b5d8/state/after_abort.json --no-park
abort_rc=127
stdout bytes=0
loop_health: ERROR: hermes CLI not found (PATH=/usr/bin:/bin, HERMES_VENV_BIN=/nonexistent-venv-dir)
loop_health: ERROR: cannot read kanban board state; refusing to silently degrade to 0 running/blocked
```

補足（設計判断の明示）: `--tasks` / `--db` 注入時は CLI 不要なので縮退させず WARN のみで継続する
（既存テストと手動注入モードの無回帰を優先）。CLI が必須の本番経路では必ず 127 で落ちる。

### 8. 回帰テスト

```
$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_loop_health.py tests/test_loop_health_business.py -q
8 passed in 37.36s
```

loop_health の不変条件テスト（top_task=最古running / business KPI gate v139 正規表現）は v141 でも緑。
リポジトリ全体では 1061 passed / 2 failed だが、失敗2件は本カードの変更と無関係
（片方は再実行で pass する順序依存の flaky、もう片方は実ボードの別カードの未復旧 rc=0 クラッシュを
数える live-DB ゲート）。

### 9. ロールバック手順

1. リポジトリ側: `git revert <本カードのコミット>`（v139 取り込み＋v141 変更が同時に戻る）
2. profile 側（symlink を実体に戻す。バックアップは本カードの作業領域に保全）:

```
$ rm /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
$ cp /tmp/t_5af1b5d8/backup/loop_health.sh.v139.orig /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
$ chmod +x /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
```

注意点（申し送り）: symlink 化により profile の物理実体が `/mnt/d` 依存になった。`/mnt/d` 未マウント時は
cron が loop_health を起動できない（既存の complete-watchdog / timeout-watch と同じ前提に揃えた）。
恒久対策は profile 配下を repo の git 管理下に置く運用（現状は repo 側が正・profile は symlink）。

### 10. 同一クラスの残存（本カードの範囲外・独立カード化）

`grep` による掃討で、cron から実行される他スクリプトに同型の bare `hermes` 呼出が残存することを確認した。
本カード t_5af1b5d8 は loop_health.sh のみを対象とするため手を入れず、追跡用の子カードを起票した。

```
$ grep -cE '(^|[^A-Za-z_"$/-])hermes[[:space:]]+kanban' /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-ready-watchdog.sh
5
```

### 11. 自己レビュー（Reflexion）

```
{"self_review":{"what_was_done":"AIチーム健康度ゲート loop_health.sh を単一ソース化（profile v139 実物を repo 追跡下へ byte 一致で移設し profile 経路を symlink 化）し、cron 最小PATHで健康度入力が無音で 0 件に縮退する bare hermes 6箇所を HERMES_BIN 解決（HERMES_VENV_BIN 前置→command -v フォールバック→解決不能時は PATH/HERMES_VENV_BIN を stderr に出して exit127）へ置換した。","what_went_well":["最小PATHの無音縮退を before(0/0) で再現し after(3/1) で実ボード値と一致させた","受入条件3の diff を 36行→0行へ、churn を排除した凍結フィクスチャ比較でも 0行で二重に示した","auto-park の comment/schedule を argv シムで捕捉し、実DB fingerprint 6項目 delta 0 を実測した","byte 一致移設を sha256/サイズで証跡化し、ロールバック手順を保全物とともに明記した"],"what_could_improve":["最初のシム実装が LOOPHEALTH_SHIM_BLOCKED を読んでおらず、破壊的経路の捕捉が1回空振りした（シム側の env 契約を先に固定すべき）","A5 の初回比較で HERMES_VENV_BIN 前置が通常PATH側の解決を上書きし、意図と違う比較になった（PATH 前置の副作用を先に読むべき）"],"mistakes_or_risks":["symlink 化で profile スクリプトの物理実体が /mnt/d 依存になった（既存 complete-watchdog と同じ前提）","同一クラスの bare hermes が kensho-ready-watchdog.sh に5箇所残る（子カードで追跡）"],"learned":"cron 最小PATHの同型バグは「縮退が正常値に見える」形で隠れるため、before/after の実測値（件数）と JSON diff を同時に取らないと再発防止になる。検証用シムは env 契約（どの変数で fixture を差し替えるか）を先に固定する。","confidence":9,"verification_evidence":"env -i PATH=/usr/bin:/bin 実走で before running/blocked=0/0・通常実行との diff 36行 → after 3/1・diff 0行（凍結フィクスチャ比較も 0行）／bare hermes 6→0／解決不能時 rc=127 で PATH と HERMES_VENV_BIN を stderr 記録／auto-park 経路は argv シムで comment+schedule を捕捉し park_action=parked、実DB fingerprint 6項目 delta 0・[loop-health] マーカー増加0／移設 sha256 5755526e... が profile・repo・バックアップで一致"}}
```

本カード t_5af1b5d8 の検証は上記で完了。
