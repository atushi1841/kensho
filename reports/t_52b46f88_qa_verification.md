## verification_evidence

### QA検証実測（2026-10-10 02:08 JST、t_52b46f88: dev.to W41-W43 内部リンク増強）

$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print('score=',d['score'],'priority=',d['priority'],'escalation=',d['escalation'],'target=',d['escalation_target'],'penalty=',d['artifact_age_penalty'])"
→ score=49 (WARN) / priority=new_proposals / escalation=true / target=t_52b46f88 / artifact_age_penalty=30

$ python3 -c "import sqlite3;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');r=c.execute('select status,started_at,claim_expires,worker_pid from tasks where id=\"t_52b46f88\"').fetchone();import datetime;print('status=',r[0],'started=',datetime.datetime.fromtimestamp(r[1]).isoformat(),'expires=',datetime.datetime.fromtimestamp(r[2]).isoformat(),'pid=',r[3])"
→ status=running / started=2026-10-10T00:47:33 / expires=2026-10-10T02:21:12 / pid=766288

$ pgrep -af "766288" | head -3
→ 766288 /home/atushi/.../python3 -m hermes_cli.main -p kensho-revenue-worker ... kanban task t_52b46f88
→ ワーカープロセス生存中（起動から1時間21分経過、TTL内）

$ ls -la /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_52b46f88/
→ weeks.py / list.py / inspect.py の3ファイルのみ（すべて診断プローブ。実装成果物ではない）

$ python3 scripts/devto_internal_links.py --list 2>&1 | grep -cE "W4[123]"
→ 4（W41-W43 記事は下書き而非公開。公開済み W41-W43 は存在しない）

$ git diff reports/apify-seo/devto-links.json | head -5
→ - "applied": true, "rows": [ 82 rows ... ]  →  + "applied": false, "rows": []
→ **既存の適用済み状態（82行・applied=true）が未適用状態（0行・applied=false）に regress**

$ cat data/apify_ppe_external_runs_state.json | python3 -c "import json,sys;d=json.load(sys.stdin);print('runs=',len(d.get('runs',[])),'last_trigger=',d.get('last_trigger'))"
→ runs=0 / last_trigger=2026-10-09T15:54:59（外部run未発火のまま）

$ cat data/gumroad_promo_kpi_state.json | python3 -c "import json,sys;d=json.load(sys.stdin);print('sales=',d['sales']['total'],'views=',d['views']['views'])"
→ sales=0 / views=0

$ cd /mnt/d/Project2/kensho && git status --porcelain | grep -E "\.(py|yaml|sh|js)$" | head -10
→ （コードファイルの未コミット変更なし。data/* と reports/* の変化のみ）

### 完了条件対応（card本文再掲）
- [ ] ① W41-W43 記事に Apify Store リンク追加（各1→6）→ **未達**。--list で W41-W43 の公開記事自体が存在しない（下書きのみ）
- [ ] ② 実行後 --list で反映確認 → **未実行**
- [x] ③ scripts/devto_internal_links.py 存在 → 実測: 7804B, git追跡済（3bcefa89）
- [ ] ④ reports/ に検証レポート → 本ファイルで生成

### Outcome（before/after）
- before: devto-links.json = applied=true / 82 rows（前回完了済の適用状態）
- after: devto-links.json = applied=false / 0 rows（ワーカーが状態を regress。W41-W43 リンク増強未実施）
- external_runs: 0 → 0（変化なし、31日連続0）
- gumroad: 0 → 0（変化なし）
