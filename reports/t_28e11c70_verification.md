# verification report for t_28e11c70

generated: 2026-09-25T16:51:30  (by kanban_done_guard.py --write-report)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは kanban_done_guard.py --write-report で機械生成されたものである。
タスクID: t_28e11c70（dominant-id 条件・所有束縛 t_23c079c5 v47 満足）

# レポジトリの最新コミット一覧（done 時の HEAD 確認用）
$ git log --oneline -5
9aad51c fix(tests): add missing 'import time' for loop_health retry path (latent NameError on JSON parse failure)
07c8cfe fix: replace resolve_max_in_progress with get_profile_cap and get_dispatcher_cap in loop_health.sh (t_28e11c70)
4fc16eb docs(evidence): t_1ab013e8 検証証跡（HEADで充足済み・再実装不要）— QA 9/25 run13
4b35eec chore: 完了カードの滞留WIPを確定（QA 9/25 run13）
435187b fix(loop_health): NameError fix for streak/score + revived card test (t_54681c2f)

# 作業ツリーの未コミット変更（条件(d) と同一規則）
$ git status --porcelain -uall
 M data/account_wifi_map.json
 M data/agent_spans/2026-09-25.jsonl
 M data/camera_monitor/7d_repro_audit.csv
 M data/collected_today.json
 M data/multi_response.json
 M data/openrouter_usage.json
 M data/self_heal_state.json
 M data/source_health.json
 M data/status/TankanNotes.json
 M data/status/atushi16.json
 M data/status/kudou.json
 M data/status/toushiwatch.json
 M data/status/zin20120731.json
 M reports/non_x_manual_20260925.md
 M reports/outcome-review-2026-09-25.md
 M revenue-status.html
?? data/camera_monitor/matched_pairs_20260925.csv
?? data/camera_monitor/model_price_diff_20260925.csv
?? data/camera_monitor/run_summary_20260925.json
?? data/camera_monitor/sourcing_candidates_20260925.csv
?? data/camera_monitor/sourcing_candidates_20260925.json
?? reports/research-20260925.md
?? reports/t_28e11c70_verification.md
?? reports/t_6f45dab0_verification.md
?? reports/t_e07dab2a_verification.md
?? scripts/check_dep_drift.py.backup
?? scripts/check_dep_drift.py.backup2
?? scripts/check_dep_drift.py.backup_before_selftest

# pytest 実行結果（条件(a)(b) 証跡）
$ python3 -m pytest -q 2>&1 | tail -5
(exec failed: Command 'python3 -m pytest -q 2>&1 | tail -5' timed out after 60 seconds)

# mypy strict チェック（0 error 確認）
$ python3 -m mypy scripts/kanban_done_guard.py 2>&1 | tail -5
mypy: can't read file 'scripts/kanban_done_guard.py': No such file or directory

