## verification_evidence

### 1. ループ健康度検証
- `$ python3 -c "import json; d=json.load(open('/home/atushi/.hermes/profiles/kensho-sweeps/data/loop_health_state.json')); print(d['score'], d['streak'], d['business_ok'], d['escalation_active'])"` → `100 0 true false`
- `$ python3 -c "import sqlite3; c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db'); print([c.execute('select count(*) from tasks where status=?',(s,)).fetchone()[0] for s in ['ready','blocked','in_progress','done','todo','scheduled']])"` → `[0, 0, 0, 734, 0, 1]`
- 判定: score=100・streak=0・healthy。前回(v35)から done 733→734（t_1d1323a5 追加）。

### 2. apify-external-runner-weekly cron 実登録 — 解消（前回の【要ユーザー対応】は解消済み）
- `$ hermes cron list 2>&1 | grep -A4 apify-external-runner-weekly` → `Name: apify-external-runner-weekly / Schedule: 0 4 * * 1 / Repeat: ∞ / Next run: 2026-10-05T04:00:00+09:00 / Deliver: telegram`
- 前回(10/05 20:16 JST)は全61ジョブに不在と検出。t_1d1323a5 の done で実登録完了。
- 証跡: `reports/t_1d1323a5_verification.md`（$ hermes cron list 実出力 + bash 実行結果 + evidence.json 全条件 pass）

### 3. Worker report 実在確認
- `$ ls -la reports/revenue-proposals/2026-10-05-revenue-worker-session.md` → 1392 bytes, 10/04 04:58
- 内容: t_ab4e4024 完了報告。dry-run 5/5 TRIGGERED（前回の「実際0」とは異なり、この報告は t_ab4e4024 時点のもの。t_1d1323a5 実行時の実出力は verification.md に記載の通り Triggered=0/Skipped=18/Failed=2）

### 4. 収益 KPI — 継続ゼロ
- `$ python3 -c "import json; d=json.load(open('data/revenue-daily.json')); print(len(d), d[-1]['date'], d[-1]['apify']['external_users_total'], d[-1]['gumroad']['products'])"` → `31 2026-10-04 0 1`
- `$ python3 -c "import json; d=json.load(open('data/revenue_health_state.json')); print(d['alert_count'], d['external_runs']['zero_days'], d['gumroad_sales']['zero_sales_days'])"` → `4 31 31`
- Gumroad: 商品1つ（$29.99・zip 545KB存在）だが sales=0。Apify external_runs=0/31日。

### 5. t_1d1323a5 証跡整合
- verification.md: `$ hermes cron list` 実出力 + `$ bash kensho_apify_external_runner_cron.sh` 実行結果（Triggered=0/Skipped=18/Failed=2/Exit 0）+ state.json 18 triggers + revenue-daily.json 追記確認 + git log 3048cb0
- evidence.json: success_indicators 5件 / verification_commands 5件 / artifact_paths 3件 / evidence_hashes 3件 / outcome {before:0, after:1}
- git log: `3048cb0 t_1d1323a5: apify_ppe_external_runner attach_to_daily KeyError耐性強化` → remote main に push 済み

### 6. 未コミットコード
- `$ git status --porcelain -- '*.py' '*.yaml' '*.sh' '*.js'` → `M kensho/orchestrator.py` + `M orchestrator.py` + MCP系 untracked（他WIP・t_ff373c55/t_dd7f5e39 系）。当QA変更なし。

### 7. t_bef61602 (Reddit新垢)
- status=scheduled, assignee=None。ユーザー手動対応待ち（karma 150達成→go.flag生成）。