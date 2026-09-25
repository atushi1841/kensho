# t_7d406997_verification

## verification_evidence

$ cd /mnt/d/Project2/kensho && grep -l '"placeholder"' reports/*_evidence.json
→ reports/t_7d406997_evidence.json

$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_7d406997 --workdir /mnt/d/Project2/kensho
→ kanban_done_guard task=t_7d406997 -> PASS (all conditions satisfied)
  j evidence.json machine-readable : True  (pass)  /mnt/d/Project2/kensho/reports/t_7d406997_evidence.json valid (fields 0 missing)

$ python3 -c "import re, json; data = json.loads(open('reports/t_7d406997_evidence.json').read()); hashes = data.get('evidence_hashes', []); pattern = r'^(sha256:)?[0-9a-f]{64}$'; bad = [h for h in hashes if not re.match(pattern, h)]; print('evidence_hashes format check:', len(bad), 'failures:', bad if bad else 'OK')"
→ evidence_hashes format check: 0 failures: OK

$ grep -c '"placeholder"' reports/t_7d406997_evidence.json
→ 0