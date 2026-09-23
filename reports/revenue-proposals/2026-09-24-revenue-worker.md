# t_e1e3592e 検証レポート — stale_lock reclaim 6件/24h（目標≤3）の構造原因と恒久手順化

- 実施: 2026-09-24 02:00〜02:30 JST（nightly-worker 5e8ec4984bba / kensho-sweeps）
- タスク: t_e1e3592e「[ループ衛生・再発2回] stale_lock reclaim 6件/24h（目標≤3）: CLI claim の worker_pid=NULL が構造原因 → claim --ttl 3600 と長ターン回避を手順化」
- 変更対象（リポジトリ外）: `~/.hermes/profiles/kensho-sweeps/cron/jobs.json` の job 5e8ec4984bba（nightly-worker）prompt のみ
- バックアップ: `~/.hermes/profiles/kensho-sweeps/cron/jobs.json.bak-ttl3600-20260924`
- リポジトリ内成果物: 本レポート + `reports/revenue-proposals/2026-09-24-revenue-worker.md` + `reports/t_e1e3592e_evidence.json`

## 実装サマリ

| 対象 | 変更 |
|------|------|
| job 5e8ec4984bba prompt 実装手順1 | `hermes kanban claim <task_id> --ttl 1800` → `--ttl 3600` |
| 同 prompt（新規2項目） | 「長ターン回避（stale_lock reclaim 対策）」: CLI claim は worker_pid=NULL で自動延長が効かない／1 claim の保持は最大50分／50分超の処理は20〜30分単位に分割して `[checkpoint]` を打つ／分割不能なら nohup で切り離し PID・ログ絶対パスを `[checkpoint]` に残す |
| 変更量 | prompt 4370 → 4759 文字（+389）。他フィールドの差分ゼロ、全ジョブ数 59 不変 |

## 構造原因の確定（コード実測）

- `hermes_cli/kanban.py:2188` — CLI claim は `kb.claim_task(conn, args.task_id, ttl_seconds=args.ttl)` を呼び **worker_pid を渡さない**
- `hermes_cli/kanban_db.py:5011-5016` — `release_stale_claims()` が延長するのは `host_local AND worker_pid AND _pid_alive(worker_pid) AND not heartbeat_stale` の4条件同時成立時のみ
- `worker_pid=NULL` のため **CLI claim は構造的に延長不能**（`hermes kanban heartbeat` も `_claimer_id()`=`host:pid` 不一致で延長不可）
- `hermes_cli/kanban_db.py:8273-8275` — reclaim payload の `host_local:false` / `prev_pid:null` は「終了対象のローカル worker プロセスが存在しない」ことの裏付け（=worker_pid NULL と整合）
- 実測: 直近24h の reclaimed 6件（t_b64c35ea ×3, t_c5097d30 ×2, t_2dccb8b3 ×1）は**全て worker_pid=None**。profile は kensho-worker / kensho-revenue-worker = nightly-worker が CLI claim で拾ったカードと一致

## verification_evidence — t_e1e3592e

(1) 修正前ベースライン（reclaimed 件数と worker_pid の実測）:

```
$ python3 /tmp/t_e1e3592e_audit.py
== reclaimed runs (last 12) ==
t_b64c35ea 09-24 01:35:01 profile=kensho-worker worker_pid=None outcome=reclaimed
    error: manual_reclaim lock=N100:3998121
    meta : {"prev_pid": null, "host_local": false, ...}
t_b64c35ea 09-24 00:57:35 profile=kensho-worker worker_pid=None outcome=reclaimed
t_b64c35ea 09-23 23:50:16 profile=kensho-worker worker_pid=None outcome=reclaimed
t_c5097d30 09-23 16:49:24 profile=kensho-revenue-worker worker_pid=None outcome=reclaimed
t_c5097d30 09-23 15:47:32 profile=kensho-revenue-worker worker_pid=None outcome=reclaimed
t_2dccb8b3 09-23 12:47:01 profile=kensho-revenue-worker worker_pid=None outcome=reclaimed
reclaimed last24h = 6
reclaimed last48h = 6
```

(2) 修正（prompt 差し替え）適用:

```
$ bash /tmp/t_e1e3592e_apply.sh
Name: nightly-worker
  Schedule: 45 * * * *
  Skills: ai-team-improvement
  Monitor: board_state_monitor.sh (agent runs only on output change)
  Continuity: on (each run sees the previous run's output)
  Workdir: /mnt/d/Project2/kensho
EXIT=0
```

(3) read-back 検証（prompt 完全一致・他フィールド無変更）:

```
$ python3 /tmp/t_e1e3592e_verify.py
1) prompt == expected file : True
2) "--ttl 3600" present    : True
3) "--ttl 1800" absent     : True
4) 長ターン回避 bullet      : True
5) prompt len              : 4370 -> 4759
6) 他フィールドの差分       : なし（promptのみ変更）
7) 全ジョブ数               : 59 -> 59
8) cron list に存在        : True Name: nightly-worker
```

(4) 成功指標その2「変更後の claim で claim_expires − claimed_at ≥ 3600」の実測:

```
$ hermes kanban claim t_e1e3592e --ttl 3600
Claimed t_e1e3592e
Workspace: /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_e1e3592e

$ python3 /tmp/t_e1e3592e_audit.py   # live claims 抜粋
  t_e1e3592e running kensho-revenue-worker lock=N100:4044243 expires_in=3597s pid=None
```

→ `expires_in=3597s`（=3600 − 実行3秒）で **≥3600 を実測で満たす**。同時に `pid=None`（構造原因の再現）も確認。

(5) 成功指標その1「reclaimed ≤3/24h」は 24h 経過しないと測れないため、計測用の検証コマンドを確定して QA カードへ引き継ぐ:

```
$ python3 -c "import sqlite3,datetime;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');s=datetime.datetime.now().timestamp()-86400;print(len(c.execute(\"select 1 from task_runs where status='reclaimed' and started_at>?\",(s,)).fetchall()))"
```

## リスクと代替案

- TTL 3600 は「60分未満の run」を救う。60分超の単一 claim は依然 reclaim されるため、prompt の「50分ルール（分割 or nohup 切り離し）」と併用が必須。
- 上流 env `HERMES_KANBAN_CLAIM_TTL_SECONDS` はコード上サポート済（`kanban_db.py:401`）。ただし gateway/サービスの env 変更＋再起動が必要で、gateway 内からの再起動はガードで禁止 → 本タスクでは採用せず、effect 未達時の代替案として温存。
- ロールバック: `cp ~/.hermes/profiles/kensho-sweeps/cron/jobs.json.bak-ttl3600-20260924 ~/.hermes/profiles/kensho-sweeps/cron/jobs.json`

## 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"CLI claim の worker_pid=NULL が stale_lock reclaim の構造原因であることをコード行と DB 実測で確定し、nightly-worker ジョブの claim --ttl を 1800→3600 に更新＋長ターン回避（50分ルール）を prompt へ手順化。read-back と claim 実測（expires_in=3597s）で検証","what_went_well":["コード根拠（kanban.py:2188 / kanban_db.py:5011-5016 / 8273-8275）と DB 実測（6件すべて worker_pid=None）を突き合わせて原因を一意に確定","hermes cron edit 経由で jobs.json を差分ゼロ（promptのみ）で更新し、バックアップと read-back 検証を実施","成功指標のうち測定可能な方（claim TTL ≥3600）を自己 claim でその場で実測"],"what_could_improve":["成功指標1（≤3/24h）は即時測定不能 → QA カードを先に用意して 24h 後に測る運用を最初から書くべきだった","jobs.json 直接編集より cron edit CLI を最初から選ぶ判断に時間を使った"],"mistakes_or_risks":["TTL 延長のみでは 60分超 run の reclaim は残る（prompt の分割運用が実効条件）","gateway 再起動が必要な env 変更案はガードで実行不可のため未採用（effect 未達時の代替として報告のみ）"],"learned":"CLI claim は worker_pid を書かないので heartbeat/延長が構造的に不可能。cron 側ワーカーは「1 claim を長時間保持しない」設計（分割＋checkpoint）で回避するのが唯一の現実解","confidence":8,"verification_evidence":"reclaimed last24h=6（全て worker_pid=None）/ prompt 4370→4759・他フィールド差分ゼロ / 自 claim の expires_in=3597s"}}
```
