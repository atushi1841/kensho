# t_e1e3592e 検証証跡 — CLI claim の worker_pid=NULL を起点とする stale_lock reclaim 対策

- タスク: **t_e1e3592e**（assignee kensho-revenue-worker / 実行者 nightly-worker 5e8ec4984bba）
- 目的: 直近24hの stale_lock reclaim 6件（目標≤3）を減らす恒久手順の確立
- 変更: `~/.hermes/profiles/kensho-sweeps/cron/jobs.json` job 5e8ec4984bba の prompt のみ（claim --ttl 1800→3600 ＋ 長ターン回避の50分ルール）
- 詳細レポート: `reports/revenue-proposals/2026-09-24-revenue-worker.md`

## 判明した構造原因（t_e1e3592e の調査結果）

- `hermes_cli/kanban.py:2188` の CLI claim は `claim_task(conn, task_id, ttl_seconds=...)` のみで **worker_pid を渡さない**
- `hermes_cli/kanban_db.py:5011-5016` の stale claim 延長条件は `host_local AND worker_pid AND _pid_alive(worker_pid) AND not heartbeat_stale` の4条件同時成立 → worker_pid が NULL の CLI claim は**延長不能で必ず reclaim**
- したがって対策は (a) TTL を延ばす (b) 1つの claim を長時間保持しない、の2点に集約される（t_e1e3592e の実装方針）

## verification_evidence — t_e1e3592e

(1) 修正前ベースライン: 直近24hの reclaimed は **6件**、全て `worker_pid=None`（=CLI claim 由来）で、これが t_e1e3592e の対象そのもの。

```
$ python3 /tmp/t_e1e3592e_audit.py
== reclaimed runs (last 12) ==
t_b64c35ea 09-24 01:35:01 profile=kensho-worker worker_pid=None outcome=reclaimed
t_c5097d30 09-23 16:49:24 profile=kensho-revenue-worker worker_pid=None outcome=reclaimed
t_2dccb8b3 09-23 12:47:01 profile=kensho-revenue-worker worker_pid=None outcome=reclaimed
reclaimed last24h = 6
reclaimed last48h = 6
```

(2) 修正の適用（prompt 差し替え、exit 0）:

```
$ bash /tmp/t_e1e3592e_apply.sh
Name: nightly-worker
  Schedule: 45 * * * *
  Skills: ai-team-improvement
  Workdir: /mnt/d/Project2/kensho
EXIT=0
```

(3) read-back 検証（prompt が期待値と完全一致・他フィールドの差分なし・ジョブ数不変）:

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

(4) 成功指標「claim_expires − claimed_at ≥ 3600」の実測（t_e1e3592e 自身を新TTLで claim）:

```
$ hermes kanban claim t_e1e3592e --ttl 3600
Claimed t_e1e3592e

$ python3 /tmp/t_e1e3592e_audit.py
  t_e1e3592e running kensho-revenue-worker lock=N100:4044243 expires_in=3597s pid=None
```

→ `expires_in=3597s` で **≥3600 を満たすことを実測**。`pid=None` も同時に確認し、構造原因の再現と対策の有効範囲（60分以内）を明示した。

(5) 残る成功指標「reclaimed ≤3/24h」の計測コマンド（24h後に QA が実行）:

```
$ python3 -c "import sqlite3,datetime;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');s=datetime.datetime.now().timestamp()-86400;print(len(c.execute(\"select 1 from task_runs where status='reclaimed' and started_at>?\",(s,)).fetchall()))"
6
```

（上記は修正直時点の値。24h後の再実行で ≤3 を判定する）
