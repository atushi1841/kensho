## verification_evidence

dominant task id: t_f5f6f8a9（本文引用9回）
worker_output_file: /mnt/d/Project2/kensho/reports/t_f5f6f8a9_verification.md

### 成果物
- dev.to記事URL: https://dev.to/atu_ino_ed473db24d76d234a/mlit-japan-property-prices-free-data-for-ai-agents-real-estate-investors-49i5
- 記事ID: 4812861
- 公開ステータス: published

### 検証コマンドと実測結果

$ curl -s -H "api-key: [REDACTED]" "https://dev.to/api/users/me"
HTTP 200, username=atu_ino_ed473db24d76d234a

$ curl -s -H "api-key: [REDACTED]" "https://dev.to/api/articles/4812861" | python3 -c "import json,sys; a=json.load(sys.stdin); print('title:',a['title'][:50]); print('published:',a.get('published',False))"
title: MLIT Japan Property Prices: Free Data for AI Agents
published: True

$ ls -la /mnt/d/Project2/kensho/reports/t_f5f6f8a9-worker-report.md
-rwxrwxrwx 1 atushi atushi 3949 Oct 7 reports/t_f5f6f8a9-worker-report.md

$ python3 -c "import json; d=json.load(open('/mnt/d/Project2/kensho/data/revenue-daily.json')); rec=d[-1]; print('external_users:',rec.get('apify',{}).get('external_users_total','n/a'))"
external_users: 0

$ cat /mnt/d/Project2/kensho/reports/t_f5f6f8a9_evidence.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('fields:', list(d.keys())); print('outcome:', d.get('outcome'))"
fields: ['task_id', 'status', 'success_indicators', 'verification_commands', 'artifact_paths', 'evidence_hashes', 'outcome']
outcome: {'metric': 'dev.to article published', 'before': 0, 'after': 1}

### KPI実績
- external_runs: 0（記事公開日=2026-10-07のため未計上）
- dev.to.views: 0（公開直後）
- 達成可否: external_run>=1は**未達成**（pending扱い）

### 代替案
記事公開自体は完了。外部流入は30日以内のmonitoring。
