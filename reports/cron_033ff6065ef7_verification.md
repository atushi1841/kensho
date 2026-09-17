# QA Nightly Report — 2026-09-17

## verification_evidence

### Loop Health
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
score=100|ready=3|blocked=2|prio=normal|streak=0|esc=False|skip=False|dirty=Y|bulk=N

### Board State
$ hermes kanban --board kensho-ai-team list --status ready --json
3 ready tasks: t_9f37e5e3 (apply調査), t_c189d8d8 (BOT対策), t_eb308533 (JEPX MCP)

$ hermes kanban --board kensho-ai-team list --status blocked --json
2 blocked: t_55210446 (GUMROAD_TOKEN), t_06fdd792 (未コミット)

### Apply Root Cause (t_9f37e5e3)
$ grep -c "OK 完了" logs/auto_20260916.log
0
$ grep -c "OK 完了" logs/auto_20260915.log
17
$ python3 -c "import sqlite3;c=sqlite3.connect('data/actions.db');print([r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])"
[]

### Test Status
$ python3 -m pytest tests/test_simple_rt_fallback.py -x --tb=short
FAILED (counter persistence: expected 2, got 6)

### Credential Check
$ echo "APIFY=$APIFY_TOKEN GUMROAD=$GUMROAD_TOKEN MLIT=$MLIT_API_KEY"
APIFY=set GUMROAD= MLIT=

### Git Status (post-push)
$ git status --porcelain -- '*.py' '*.yaml' '*.sh' '*.js'
(no output = clean)

### Apify API Check
$ curl -s -m 10 -H "Authorization: Bearer $APIFY_TOKEN" https://api.apify.com/v2/acts/fruitful_quintessence~japan-used-camera-market-scraper | python3 -c "import sys,json;print(json.load(sys.stdin).get('billing','N/A'))"
N/A