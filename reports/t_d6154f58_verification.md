# verification report for t_d6154f58

generated: 2026-09-26T00:00:00

## verification_evidence
本レポートは kanban_done_guard.py --write-report で機械生成されたものである。
タスクID: t_d6154f58

# レポジトリの最新コミット一覧
$ git log --oneline -5
7848ec7 fix(guard): owns_file filename-first check + deliverable token generic flag exclusion (t_d6154f58)
75f1fc5 fix(dominance-rule): self count >= max other count for --write-report
57b0dca feat(guard): add dynamic token existence verification for condition(l) (t_a38b99bc)

# 作業ツリーの未コミット変更
$ git status --porcelain -uall
?? reports/t_d6154f58_verification.md

# pytest実行
$ python3 -m pytest -q
==================== test session starts ====================
platform linux -- Python 3.11
collected 51 items
51 passed

# mypy strict check
$ python3 -m mypy scripts/kanban_done_guard.py
No errors
