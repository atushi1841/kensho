# verification report for t_28e11c70

generated: 2026-09-25T19:13:37  (by kanban_done_guard.py --write-report)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは kanban_done_guard.py --write-report で機械生成されたものである。
タスクID: t_28e11c70（dominant-id 条件・所有束縛 t_23c079c5 v47 満足）

# レポジトリの最新コミット一覧（done 時の HEAD 確認用）
$ git log --oneline -5
2c5a6a4 Fix: Add kanban.max_in_progress to config.yaml and commit check_dep_drift.py
b95e195 t_a38b99bc: add verification report for deliverable token check
4b34477 fix: add requirements-lock check to drift detection
2bde89b docs(evidence): QA nightly-qa run15 — guard --selftest 回帰の親コミット比較確定(ff2a357=0/e079f50=2)・blocked 2→6 内訳・OWNED誤帰属の実測 (2026-09-25)
e90782e docs(revenue): 2026-09-25 v4 — criticレポートの収益可視化復元＋Gumroad鮮度・失効追加 (t_61d0db99 受入基準3)

# 作業ツリーの未コミット変更（条件(d) と同一規則）
$ git status --porcelain -uall
 M config.yaml
 M data/account_wifi_map.json
 M data/agent_spans/2026-09-25.jsonl
 M data/camera_monitor/7d_repro_audit.csv
 M data/collected_today.json
 M data/multi_response.json
 M data/openrouter_usage.json
 M data/revenue-daily.json
 M data/self_heal_state.json
 M data/source_health.json
 M data/status/TankanNotes.json
 M data/status/atushi16.json
 M data/status/kudou.json
 M data/status/toushiwatch.json
 M data/status/zin20120731.json
 M reports/non_x_manual_20260925.md
 M reports/outcome-review-2026-09-25.md
 M reports/t_031f04b9_verification.md
 M reports/t_ebbfe4a7_verification.md
 M revenue-status.html
 M scripts/kensho_revenue_collect.py
 M scripts/loop_health.sh
 M tests/test_loop_health.py
?? data/camera_monitor/matched_pairs_20260925.csv
?? data/camera_monitor/model_price_diff_20260925.csv
?? data/camera_monitor/run_summary_20260925.json
?? data/camera_monitor/sourcing_candidates_20260925.csv
?? data/camera_monitor/sourcing_candidates_20260925.json
?? reports/research-20260925.md
?? reports/t_28e11c70_evidence.json
?? reports/t_6f45dab0_verification.md
?? reports/t_757b8b5d_evidence.json
?? reports/t_757b8b5d_verification.md
?? reports/t_e07dab2a_verification.md
?? reports/t_fe629b9e_verification.md
?? scripts/check_dep_drift.py.backup
?? scripts/check_dep_drift.py.backup2
?? scripts/check_dep_drift.py.backup_before_selftest
?? scripts/loop_health.sh.bak
?? scripts/revenue_record_reconcile.py
?? tests/test_revenue_record_reconcile.py

# pytest 実行結果（条件(a)(b) 証跡）
$ python3 -m pytest -q 2>&1 | tail -5
(exec failed: Command 'python3 -m pytest -q 2>&1 | tail -5' timed out after 60 seconds)

# mypy strict チェック（0 error 確認）
$ python3 -m mypy scripts/kanban_done_guard.py 2>&1 | tail -5
mypy: can't read file 'scripts/kanban_done_guard.py': No such file or directory

