# verification report for t_9e947f54

generated: 2026-10-09T19:44:35  (by kanban_done_guard.py --write-report)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは kanban_done_guard.py --write-report で機械生成されたものである。
タスクID: t_9e947f54（dominant-id 条件・所有束縛 t_23c079c5 v47 満足）

# レポジトリの最新コミット一覧（done 時の HEAD 確認用）
$ git log --oneline -5
7595f81 t_9e947f54: actor_weekly_run.py + verification evidence
887a06e t_9e947f54: critic observation and proposal for actor weekly run visibility
b7d71ee t_bb95ba8a: dev.to X拡散スクリプト追加
89a5399 t_4ec96eb8: fix verification evidence format
0a918b4 t_4ec96eb8: verification evidence and test fix

# 作業ツリーの未コミット変更（条件(d) と同一規則）
$ git status --porcelain -uall
 M data/account_wifi_map.json
 M data/apify_actors_detail_snapshot.json
 M data/automation_block.json
 M data/collected_today.json
 M data/competition_score.json
 M data/gumroad_promo_kpi_state.json
 M data/gumroad_views_history.json
 M data/multi_response.json
 M data/revenue-daily.json
 M data/revenue_health_state.json
 M data/self_heal_state.json
 M data/source_health.json
 M data/status/TankanNotes.json
 M data/status/atushi16.json
 M data/status/kudou.json
 M data/status/source_new_day.json
 M data/status/toushiwatch.json
 M data/status/zin20120731.json
 M kensho/scraping/collector.py
 M kensho/scraping/sources/__init__.py
 M mcp_servers/japan_ec_mcp
 M payload.json
 M reports/apify-seo/devto-links.json
 M reports/critic-observe-2026-10-08.md
 M reports/critic-observe-2026-10-09.md
 M reports/critic-observe-2026-10-10.md
 M reports/journalism/drafts/devto-2026W39.md
 M reports/journalism/drafts/devto-2026W40-en.md
 M reports/journalism/drafts/devto-2026W40.md
 M reports/journalism/drafts/devto-2026W41.md
 M reports/journalism/drafts/devto-2026W42.md
 M reports/journalism/drafts/devto-2026W43.md
 M reports/journalism/drafts/devto-2026W44-mcp-intro.md
 M reports/journalism/drafts/devto-anime-figure-weekly-2026W41.md
 M reports/journalism/drafts/devto-mlit-property-2026.md
 M reports/journalism/drafts/qiita-2026W39.md
 M reports/journalism/drafts/qiita-2026W40.md
 M reports/journalism/drafts/qiita-2026W41.md
 M reports/journalism/drafts/qiita-2026W42.md
 M reports/journalism/drafts/qiita-2026W43.md
 M reports/journalism/drafts/qiita-apify-actors-2026W41.md
 M reports/kanban_deadlock_state.json
 M reports/revenue-proposals/2026-09-05-overseas-saas-monitor.md
 M reports/t_3903ecdb_verification.md
 M reports/t_b71a800a_verification.md
 M reports/t_e3e0d19c_verification.md
 M revenue-status.html
 M scripts/apify_run_monitor.py
 M scripts/loop_health.sh
?? .github/workflows/apify-readme.yml
?? apply_readme_fix.py
?? config.yaml.tmp
?? data/agent_spans/2026-10-08.jsonl
?? data/agent_spans/2026-10-09.jsonl
?? data/compensation_state.json
?? data/smithery_usecount_20261009_115436.json
?? data/smithery_usecount_20261009_121641.json
?? data/smithery_usecount_20261009_122950.json
?? data/x_session_c.json.bak20261009-150144
?? data/x_session_c.json.bak20261009-160341
?? data/x_session_c.json.bak20261009-180329
?? data/x_session_c.json.bak20261009-190124
?? dataset_readme.md
?? kensho/scraping/sources/appare.py
?? kensho/scraping/sources/mechatoku.py
?? reports/.hermes-tmp.cYQLOA
?? reports/.hermes-tmp.t0t4SN
?? reports/033ff6065ef7_qa_verification_20261010.md
?? reports/033ff6065ef7_qa_verification_20261010_v2.md
?? reports/gh-trend-candidates-2026-10-09.json
?? reports/gh-trend-candidates-2026-10-09.md
?? reports/non_x_manual_20261008.md
?? reports/non_x_manual_20261009.md
?? reports/outcome-review-2026-10-08.md
?? reports/outcome-review-2026-10-09.md
?? reports/outcome-review-2026-10-10.md
?? reports/qa_20261010_evidence.json
?? reports/qa_20261010_summary.md
?? reports/qa_output_20261008.md
?? reports/qa_output_20261008_final.md
?? reports/qa_output_20261008_short.md
?? reports/research-20261008.md
?? reports/research-20261023.md
?? reports/revenue-proposals/2026-10-08-revenue-worker-v1.md
?? reports/revenue-proposals/qa-2026-10-08.md
?? reports/revenue-qa-2026-10-10-v3.md
?? reports/revenue-qa-2026-10-10-v4.md
?? reports/t_0b856e2c_evidence.json
?? reports/t_400af3f9_evidence.json
?? reports/t_QA_smithery_verification_2026-10-10.md
?? reports/t_d1df914c_evidence.json
?? reports/t_daa6f362_evidence.json
?? reports/verification_evidence.txt
?? reports/verification_evidence_section.txt
?? scripts/add_mcp_smithery_links.py
?? scripts/add_smithery_links.py
?? tests/.hermes-tmp.BvpeZO
?? tests/test_appare_scraper.py
?? tests/test_mechatoku_scraper.py
?? typescript

# pytest 実行結果（条件(a)(b) 証跡）
$ python3 -m pytest -q 2>&1 | tail -5
/home/atushi/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3: No module named pytest

# mypy strict チェック（0 error 確認）
$ python3 -m mypy scripts/kanban_done_guard.py 2>&1 | tail -5
/home/atushi/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3: No module named mypy

