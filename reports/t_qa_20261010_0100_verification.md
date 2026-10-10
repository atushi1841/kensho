## verification_evidence

### ループ健康度（loop_health.sh 実測）
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(json.dumps({k:d[k] for k in ['score','stagnation_streak','priority','alert','escalation']},ensure_ascii=False))"
{"score": 39, "stagnation_streak": 1, "priority": "normal", "alert": "WARN", "escalation": true}

### Kanban board 状態（sqlite 直叩き）
$ python3 -c "import sqlite3;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');[print(s,c.execute('select count(*) from tasks where status=?',(s,)).fetchone()[0]) for s in ['ready','blocked','in_progress','done','todo']]"
ready 1 / blocked 0 / in_progress 3 / done 880 / todo 0

### 実行中タスク（年齢）
$ python3 -c "import sqlite3,time;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');now=time.time();[print(r[0],r[1][:40],f'age={(now-r[3])/3600:.1f}h') for r in c.execute(\"select id,title,created_at from tasks where status='in_progress' order by created_at\")]"
t_c42a9eb6 週次PPE外部run自動化パイプライン age=0.2h
t_09435cb2 Qiita既存Draft(10本)を一括public化 age=1.2h
t_974844f8 Kanbanカードテンプレート完了条件必須化 age=1.8h

### 証跡ファイル存在確認
$ ls -la /mnt/d/Project2/kensho/reports/{t_c42a9eb6,t_974844f8,t_09435cb2}_verification.md
t_c42a9eb6: MISSING
t_974844f8: MISSING
t_09435cb2: 2743B OK

### 収益メトリクス
$ python3 -c "import json;d=json.load(open('/mnt/d/Project2/kensho/data/apify_ppe_external_runs_state.json'));print(len(d.get('last_trigger',{})),'triggers recorded')"
13 triggers recorded (2026-10-07〜2026-10-09)

$ cat /mnt/d/Project2/kensho/data/actor_weekly_run_state.json | python3 -c "import json,sys;d=json.load(sys.stdin);print(json.dumps(d,ensure_ascii=False)[:300])"
{"2026-W41": {"a": {"whSePszWpMtfeLYBp": {"error": "HTTP 400", "devto_url": "https://dev.to/atu_ino_..."}}}}

### 作成済み資産
$ ls -la /mnt/d/Project2/kensho/templates/kanban-card-body-template.md
-rwxrwxrwx 1 atushi atushi 663B Oct 10 00:04

$ ls -la /mnt/d/Project2/kensho/scripts/apify_ppe_external_runner.py
-rwxrwxrwx 1 atushi atushi 18134B Oct 7 10:43

### 前回実行エラー
$ hermes cron list 2>&1 | grep -A3 "nightly-qa"
Last run: 2026-10-09T23:13:16  error: RuntimeError: The model's action arrived cut off partway through