# t_20f49e54 検証証跡

## verification_evidence
$ python3 -m pytest tests/test_done_guard_evidence_binding.py -q
5 passed in 0.12s
$ grep -c "source_commits" ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py
0
$ git log --oneline -1
ea78e29 Add done_guard evidence binding tests
