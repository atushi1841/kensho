## verification_evidence

### 実測コマンドとその出力

$ python3 -c "import json; d=json.load(open('/home/atushi/.hermes/profiles/kensho-sweeps/data/loop_health_state.json')); print(json.dumps({k:d[k] for k in ['score','streak','escalation_active','business_ok','last_run_ts']}, indent=2))"
{
  "score": 100,
  "streak": 0,
  "escalation_active": false,
  "business_ok": true,
  "last_run_ts": "2026-10-02T08:26:07+09:00"
}
--

$ python3 -c "import sqlite3; db='/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db'; c=sqlite3.connect(db); [print(s, c.execute('select count(*) from tasks where status=?',(s,)).fetchone()[0]) for s in ['ready','blocked','in_progress','todo','done','archived','scheduled']]"
ready 0
blocked 0
in_progress 0
todo 0
done 707
archived 192
scheduled 1
--

$ python3 -c "
import sqlite3
db='/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db'
c=sqlite3.connect(db)
for r in c.execute(\"select id,title,status,assignee from tasks where status in ('running','in_progress','scheduled')\"):
    print(r)
"
('t_f859baf0', 'Japan Event and Festival Data Scraper (Matsuri/Concert/Exhibition)', 'running', 'kensho-worker')
('t_bef61602', '[新垢] Reddit新アカウント+週1価値提供投稿パイプライン', 'scheduled', None)
--

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/reddit-gate-check.sh; echo exit=$?
== reddit gate check 2026-10-02 09:08:26 JST ==
PASS G0: cookie ok (11 entries, reddit_session=True csrf=True)
PASS G1: date ok (today=2026-10-02 >= resume_from=2026-09-28)
FAIL G2: no go.flag - user must enable phone tethering then run: touch /mnt/d/Project2/kensho/data/reddit/go.flag
PASS G3: queue ok (OK DataSets 184)
PASS G4: identity ok (u/sabotenJAL == expected u/sabotenJAL)
FAIL G5: account too young (sabotenJAL age_days=25 < 30)
PASS G6: submitter present (/mnt/d/Project2/kensho/data/reddit/cdp_submit_v2.js)
--
GATES: FAIL (2 gate(s) blocked) -> DO NOT POST
exit=1
--

$ python3 -c "
import json
with open('/mnt/d/Project2/kensho/data/revenue-daily.json') as f:
    d=json.load(f)
print('entries:', len(d))
print('latest:', d[-1].get('date'))
print('external_users_total:', sum(e.get('external_users',0) for e in d))
print('revenue_usd:', sum(e.get('revenue_usd',0) for e in d))
"
entries: 29
latest: 2026-10-01
external_users_total: 0
revenue_usd: 0
--

$ ls /mnt/d/Project2/kensho/reports/revenue-proposals/2026-10-06* 2>/dev/null || echo "NO_TODAY_WORKER_REPORT"
NO_TODAY_WORKER_REPORT
--

$ python3 -c "
import json,os,time
pq='/mnt/d/Project2/kensho/data/reddit/post_queue.json'
mtime=os.path.getmtime(pq)
age_hours=(time.time()-mtime)/3600
print('post_queue age_hours:', round(age_hours,1))
"
post_queue age_hours: 40.8
--

$ git -C /mnt/d/Project2/kensho status --porcelain 2>/dev/null | grep -cE '\.(py|yaml|sh|js)$'
203
--

$ git -C /mnt/d/Project2/kensho log --oneline -3
fa3eb21 docs(revenue): Reddit gate recheck #9 (2026-10-02 08:26 JST) - G2/G5 FAIL unchanged, Phase 1 user-action-required
529b01a docs(evidence): t_c712b42b Japan Travel Scraper feasibility report
e4451d0 tcg-price-collect: append dataset snapshot (2026-10-01 22:30:13Z)
--