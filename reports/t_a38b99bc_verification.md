# verification report for t_a38b99bc

generated: 2026-09-25T19:32:15  (by kanban_done_guard.py --write-report)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは kanban_done_guard.py --write-report で機械生成されたものである。
タスクID: t_a38b99bc（dominant-id 条件・所有束縛 t_23c079c5 v47 満足）

# レポジトリの最新コミット一覧（done 時の HEAD 確認用）
$ git log --oneline -5
eefb439 docs(evidence): QA run16 追記 — t_28e11c70 の巻き込みcommit(df91ceb)と running=5>cap4 の実測 (2026-09-25)
df91ceb Finalize all changes for t_28e11c70
de498d7 Add evidence.json for t_28e11c70 verification
19b3eea Add verification report for t_28e11c70
2c5a6a4 Fix: Add kanban.max_in_progress to config.yaml and commit check_dep_drift.py

# 作業ツリーの未コミット変更（条件(d) と同一規則）
$ git status --porcelain -uall
 M data/account_wifi_map.json
 M data/status/TankanNotes.json
 M data/status/atushi16.json
 M data/status/kudou.json
 M data/status/toushiwatch.json
 M data/status/zin20120731.json
?? reports/t_41df6e84_verification.md

# pytest 実行結果（条件(a)(b) 証跡）
$ python3 -m pytest -q 2>&1 | tail -5
(exec failed: Command 'python3 -m pytest -q 2>&1 | tail -5' timed out after 60 seconds)

# mypy strict チェック（0 error 確認）
$ python3 -m mypy scripts/kanban_done_guard.py 2>&1 | tail -5
mypy: can't read file 'scripts/kanban_done_guard.py': No such file or directory

