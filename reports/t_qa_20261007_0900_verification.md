# QA verification report — t_7d5d5ed1

**Task**: MCP/APify可視性信号強化: Smithery description埋め+GitHub/APify双向链接
**Date**: 2026-10-07 09:00 JST
**QA**: kensho-sweeps (nightly-qa)

## verification_evidence

$ hermes kanban --board kensho-ai-team show t_7d5d5ed1 | head -5
→ status=running / assignee=kensho-revenue-worker / created=2026-10-04

$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_7d5d5ed1 --workdir /mnt/d/Project2/kensho 2>&1 | head -5
→ kanban_done_guard task=t_7d5d5ed1 -> PASS (all conditions satisfied)

$ python3 -c "import json; d=json.load(open('/mnt/d/Project2/kensho/reports/t_7d5d5ed1_evidence.json')); print('fields:', len(d), '/ success_indicators:', len(d.get('success_indicators',[])), '/ verification_commands:', len(d.get('verification_commands',[])), '/ artifact_paths:', len(d.get('artifact_paths',[])), '/ evidence_hashes:', len(d.get('evidence_hashes',[])))"
→ fields: 6 / success_indicators: 3 / verification_commands: 3 / artifact_paths: 6 / evidence_hashes: 6

$ ls -l /mnt/d/Project2/kensho/mcp/kensho-kema/manifest.json /mnt/d/Project2/kensho/mcp/kensho-kema/server.mcpb
→ -rwxrwxrwx 1 atushi atushi ... manifest.json
   -rwxrwxrwx 1 atushi atushi ... server.mcpb

$ git -C /mnt/d/Project2/kensho log --oneline -1
→ 50255bf manifest repositoryUrl/homepageUrl 追加 (t_7d5d5ed1 step1)
