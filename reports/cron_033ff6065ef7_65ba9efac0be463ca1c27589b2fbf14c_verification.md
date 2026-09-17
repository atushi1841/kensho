# QA Nightly Report — cron:033ff6065ef7:65ba9efac0be463ca1c27589b2fbf14c

## verification_evidence

### Loop Health
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
score=100|ready=3|blocked=2|prio=normal|streak=0|esc=False|skip=False|dirty=Y|bulk=N

### Board State (kensho-ai-team)
$ hermes kanban --board kensho-ai-team list --status ready --json
ready=3: t_9f37e5e3, t_c189d8d8, t_eb308533

$ hermes kanban --board kensho-ai-team list --status blocked --json
blocked=2: t_55210446, t_06fdd792

### Apply Root Cause (t_9f37e5e3)
$ grep -c "OK 完了" logs/auto_20260916.log
0
$ grep -c "OK 完了" logs/auto_20260915.log
17

### Test Status
$ python3 -m pytest tests/test_simple_rt_fallback.py -x --tb=short
FAILED (counter persistence)

### Credential Check
$ echo "APIFY=$APIFY_TOKEN GUMROAD=$GUMROAD_TOKEN MLIT=$MLIT_API_KEY"
APIFY=set GUMROAD= MLIT=